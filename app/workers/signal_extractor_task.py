"""Celery tasks for behavioral signal extraction.

Wraps the async signal-extractor service as synchronous Celery tasks,
supporting both single-event and batch processing modes.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import current_task

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Single-event extraction
# ---------------------------------------------------------------------------


@celery_app.task(
    name="app.workers.signal_extractor.extract_signals",
    queue="signal_extraction",
    max_retries=2,
    acks_late=True,
    bind=True,
)
def extract_signals(self, event: dict) -> dict:
    """Extract DISC signals from a single behavioral event.

    Wraps :func:`process_behavioral_events` with a one-element list so the
    full validation → extraction → confidence pipeline runs on the event.

    Args:
        event: Raw behavioral event dict.  Expected keys include at least
            ``event_type``, ``platform``, ``timestamp``, and optionally
            ``user_id`` plus platform-specific payload fields.

    Returns:
        dict with extracted signals, confidence scores, and status flags.
        See :func:`process_behavioral_events` for the full schema.
    """
    from app.services.signal_extractor.worker import process_behavioral_events

    task_id = current_task.request.id if current_task else None
    user_id = event.get("user_id")

    logger.info(
        "extract_signals started  task_id=%s  user_id=%s  event_type=%s",
        task_id,
        user_id,
        event.get("event_type"),
    )

    try:
        result: dict[str, Any] = _run_async(
            process_behavioral_events(
                events=[event],
                user_id=user_id,
            )
        )

        result["task_id"] = task_id

        if result.get("success"):
            logger.info(
                "extract_signals succeeded  task_id=%s  signals=%d",
                task_id,
                result.get("signal_count", 0),
            )
        else:
            logger.warning(
                "extract_signals failed  task_id=%s  error=%s",
                task_id,
                result.get("error"),
            )

        return result

    except Exception as exc:
        logger.exception("extract_signals failed  task_id=%s", task_id)
        try:
            self.retry(exc=exc, countdown=2 ** self.request.retries * 15)
        except self.MaxRetriesExceededError:
            return _error(f"Max retries exceeded: {exc}", task_id=task_id)


# ---------------------------------------------------------------------------
# Batch extraction
# ---------------------------------------------------------------------------


@celery_app.task(
    name="app.workers.signal_extractor.extract_signals_batch",
    queue="signal_extraction",
    max_retries=2,
    acks_late=True,
    bind=True,
)
def extract_signals_batch(self, events: list[dict]) -> dict:
    """Extract DISC signals from a batch of behavioral events.

    All events are passed through the full pipeline in a single call to
    :func:`process_behavioral_events`.  Use this when ingesting a stream
    of events (e.g. from Kafka) for better throughput compared to
    dispatching one task per event.

    Args:
        events: List of raw behavioral event dicts.

    Returns:
        dict with aggregated extraction results:

        * **signals** – all extracted signals across the batch.
        * **confidence** – per-dimension confidence after processing
          the entire batch.
        * **overall_confidence** – combined confidence score.
        * **signal_count** – total signals extracted.
        * **valid_events** / **invalid_events** – validation counts.
        * **batch_size** – number of input events.
        * **success** / **error** – status fields.
    """
    from app.services.signal_extractor.worker import process_behavioral_events

    task_id = current_task.request.id if current_task else None
    batch_size = len(events) if events else 0

    logger.info(
        "extract_signals_batch started  task_id=%s  batch_size=%d",
        task_id,
        batch_size,
    )

    if not events:
        return {
            **_error("Empty event batch", task_id=task_id),
            "batch_size": 0,
        }

    # Determine user_id from the batch (if all events share one)
    user_ids = {e.get("user_id") for e in events if e.get("user_id")}
    user_id = user_ids.pop() if len(user_ids) == 1 else None

    try:
        result: dict[str, Any] = _run_async(
            process_behavioral_events(
                events=events,
                user_id=user_id,
            )
        )

        result["task_id"] = task_id
        result["batch_size"] = batch_size

        if result.get("success"):
            logger.info(
                "extract_signals_batch succeeded  task_id=%s  "
                "batch_size=%d  signals=%d  valid=%d  invalid=%d",
                task_id,
                batch_size,
                result.get("signal_count", 0),
                result.get("valid_events", 0),
                result.get("invalid_events", 0),
            )
        else:
            logger.warning(
                "extract_signals_batch failed  task_id=%s  error=%s",
                task_id,
                result.get("error"),
            )

        return result

    except Exception as exc:
        logger.exception("extract_signals_batch failed  task_id=%s", task_id)
        try:
            self.retry(exc=exc, countdown=2 ** self.request.retries * 15)
        except self.MaxRetriesExceededError:
            return {
                **_error(f"Max retries exceeded: {exc}", task_id=task_id),
                "batch_size": batch_size,
            }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _error(
    message: str,
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Build a standardised error response."""
    return {
        "signals": [],
        "confidence": {"D": 0.0, "I": 0.0, "S": 0.0, "C": 0.0},
        "overall_confidence": 0.0,
        "signal_count": 0,
        "valid_events": 0,
        "invalid_events": 0,
        "validation_errors": [],
        "success": False,
        "error": message,
        "task_id": task_id,
    }
