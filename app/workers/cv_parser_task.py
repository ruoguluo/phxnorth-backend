"""Celery task for CV parsing pipeline.

Wraps the async CV parser service as a synchronous Celery task,
handling file retrieval, parsing, signal extraction, and triggering
downstream DISC recomputation.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any

from celery import current_task

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Should not happen in a Celery worker, but guard anyway
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop exists – create one
        return asyncio.run(coro)


@celery_app.task(
    name="app.workers.cv_parser.process_cv_upload",
    queue="cv_parsing",
    max_retries=3,
    acks_late=True,
    bind=True,
)
def process_cv_upload(self, message: dict) -> dict:
    """Full CV parsing pipeline as a Celery task.

    Accepts a message dict with either an S3 key for file retrieval or
    inline raw text.  Orchestrates:

    1. Fetch raw text from *message* (``s3_key`` **or** ``raw_text``).
    2. Write to a temp file and call ``parse_cv()``.
    3. Extract career signals (handled inside ``parse_cv``).
    4. Return structured result.
    5. Trigger DISC recomputation for the user.

    Args:
        message: Dict with keys:
            - ``user_id`` (str): required – the user whose CV this is.
            - ``s3_key`` (str, optional): S3 object key for the uploaded file.
            - ``raw_text`` (str, optional): pre-extracted text content.
            - ``file_name`` (str, optional): original filename (used for
              extension detection when writing temp files).
            - ``file_extension`` (str, optional): e.g. ``".pdf"``, ``".docx"``.

    Returns:
        dict with parse results, metadata, and status flags.
    """
    from app.services.cv_parser.parser import parse_cv

    user_id: str | None = message.get("user_id")
    s3_key: str | None = message.get("s3_key")
    raw_text: str | None = message.get("raw_text")
    file_name: str | None = message.get("file_name")
    file_extension: str = message.get("file_extension", ".pdf")

    task_id = current_task.request.id if current_task else None

    logger.info(
        "process_cv_upload started  task_id=%s  user_id=%s  s3_key=%s",
        task_id,
        user_id,
        s3_key,
    )

    if not user_id:
        return _error("user_id is required", task_id=task_id)

    # ------------------------------------------------------------------
    # 1. Obtain file content
    # ------------------------------------------------------------------
    temp_path: Path | None = None
    try:
        if s3_key:
            # Fetch file bytes from S3 (or compatible object store)
            file_bytes = _fetch_from_s3(s3_key)
            if file_bytes is None:
                return _error(
                    f"Failed to fetch file from S3: {s3_key}",
                    task_id=task_id,
                    user_id=user_id,
                )
            suffix = Path(file_name).suffix if file_name else file_extension
            temp_path = _write_temp_file(file_bytes, suffix=suffix)

        elif raw_text:
            # Write raw text to a temp file so the parser can process it
            suffix = Path(file_name).suffix if file_name else file_extension
            temp_path = _write_temp_file(raw_text.encode("utf-8"), suffix=suffix)

        else:
            return _error(
                "Either s3_key or raw_text must be provided",
                task_id=task_id,
                user_id=user_id,
            )

        # ------------------------------------------------------------------
        # 2–3. Parse CV (includes section classification, job extraction,
        #       duration calculation, career analytics, and signal extraction)
        # ------------------------------------------------------------------
        result: dict[str, Any] = _run_async(parse_cv(temp_path, user_id=user_id))

        # Attach task metadata
        result["task_id"] = task_id
        result["user_id"] = user_id

        # ------------------------------------------------------------------
        # 4. Trigger downstream DISC recomputation
        # ------------------------------------------------------------------
        if result.get("success"):
            _trigger_disc_recomputation(user_id, result)
            logger.info(
                "process_cv_upload succeeded  task_id=%s  user_id=%s  signals=%d",
                task_id,
                user_id,
                len(result.get("signals", [])),
            )
        else:
            logger.warning(
                "process_cv_upload parse failed  task_id=%s  error=%s",
                task_id,
                result.get("error"),
            )

        return result

    except Exception as exc:
        logger.exception("process_cv_upload failed  task_id=%s", task_id)
        # Retry with exponential backoff on transient errors
        try:
            self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
        except self.MaxRetriesExceededError:
            return _error(
                f"Max retries exceeded: {exc}",
                task_id=task_id,
                user_id=user_id,
            )

    finally:
        # Clean up temp file
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                logger.warning("Failed to delete temp file: %s", temp_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_from_s3(s3_key: str) -> bytes | None:
    """Fetch a file from S3 (or compatible object store).

    Returns the file content as bytes, or ``None`` on failure.
    This is a thin wrapper so it can be easily mocked in tests.
    """
    try:
        import boto3

        from app.config import get_settings

        settings = get_settings()
        s3_client = boto3.client("s3")
        bucket = getattr(settings, "s3_bucket", "phxnorth-uploads")
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        return response["Body"].read()
    except Exception:
        logger.exception("S3 fetch failed for key=%s", s3_key)
        return None


def _write_temp_file(content: bytes, suffix: str = ".pdf") -> Path:
    """Write *content* to a named temporary file and return its path.

    The caller is responsible for cleaning up the file.
    """
    tmp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
        prefix="cv_upload_",
    )
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


def _trigger_disc_recomputation(user_id: str, parse_result: dict) -> None:
    """Fire-and-forget DISC profile recomputation for *user_id*.

    Sends the task to the ``disc_scoring`` queue.  If the task isn't
    registered yet (the disc_scorer worker hasn't been deployed), the
    message sits in the queue until a consumer picks it up.
    """
    try:
        celery_app.send_task(
            "app.workers.disc_scorer.recompute_disc_profile",
            kwargs={
                "user_id": user_id,
                "source": "cv_parser",
                "signal_count": len(parse_result.get("signals", [])),
            },
            queue="disc_scoring",
        )
        logger.info(
            "Triggered DISC recomputation for user_id=%s",
            user_id,
        )
    except Exception:
        # Non-critical – log and move on
        logger.exception(
            "Failed to trigger DISC recomputation for user_id=%s",
            user_id,
        )


def _error(
    message: str,
    *,
    task_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Build a standardised error response."""
    return {
        "success": False,
        "error": message,
        "task_id": task_id,
        "user_id": user_id,
        "raw_text": "",
        "sections": [],
        "job_entries": [],
        "durations": {},
        "analytics": {},
        "signals": [],
        "metadata": {},
        "parser_version": None,
    }
