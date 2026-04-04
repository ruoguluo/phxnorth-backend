"""CV upload and parsing endpoints."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.api.deps import get_current_user, get_kafka_producer
from app.api.v1.schemas.cv import CVStatusResponse, CVTextRequest, CVUploadResponse
from app.kafka.schemas import CVUploadMessage
from app.kafka.topics import KafkaTopic
from app.services.cv_parser.parser import parse_cv

if TYPE_CHECKING:
    from app.kafka.producer import KafkaProducerService
    from app.models.user import User

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["cv"])

# In-memory job store — replaced by DB persistence in later phases
_job_store: dict[UUID, dict[str, Any]] = {}

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/users/{user_id}/cv/upload",
    response_model=CVUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a CV file (PDF/DOCX)",
    description="Upload a PDF or DOCX file for parsing. Returns a job ID for status polling.",
)
async def upload_cv_file(
    user_id: UUID,
    file: UploadFile,
    _current_user: User = Depends(get_current_user),
    kafka_producer: KafkaProducerService | None = Depends(get_kafka_producer),
) -> CVUploadResponse:
    """Accept a CV file upload, parse it, and store the result.

    If a Kafka producer is available the file metadata is published to
    ``raw.cv.uploads`` and a 202 is returned immediately.  Otherwise the
    endpoint falls back to synchronous in-process parsing.

    Args:
        user_id: Target user ID from the path.
        file: Uploaded PDF or DOCX file.
        kafka_producer: Optional Kafka producer injected by FastAPI.

    Returns:
        CVUploadResponse with a job_id for status polling.

    Raises:
        HTTPException 400: If file type is unsupported or file is too large.
    """
    # Validate file extension
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read file contents and validate size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large ({len(contents)} bytes). Maximum allowed: {MAX_FILE_SIZE} bytes (10 MB).",
        )

    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    job_id = uuid4()

    logger.info(
        "cv.upload.started",
        job_id=str(job_id),
        user_id=str(user_id),
        filename=filename,
        size=len(contents),
    )

    # --- Kafka path: publish and return 202 immediately ---
    published = False
    if kafka_producer is not None:
        try:
            message = CVUploadMessage(
                user_id=str(user_id),
                source="upload",
                s3_key=f"cv-uploads/{user_id}/{job_id}{suffix}",
                raw_text="",  # Raw text extracted by the consumer
                filename=filename,
                event_id=str(job_id),
            )
            await kafka_producer.send(
                topic=KafkaTopic.RAW_CV_UPLOADS.value,
                message=message.to_dict(),
                key=str(user_id),
            )
            published = True
            logger.info(
                "cv.upload.published_to_kafka",
                job_id=str(job_id),
                user_id=str(user_id),
                topic=KafkaTopic.RAW_CV_UPLOADS.value,
            )
        except Exception:
            logger.warning(
                "cv.upload.kafka_publish_failed",
                job_id=str(job_id),
                user_id=str(user_id),
                exc_info=True,
            )

    # --- Synchronous fallback: parse in-process ---
    if not published:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(contents)
            tmp.flush()

            result = await parse_cv(file_path=tmp.name, user_id=user_id)

        _job_store[job_id] = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "completed" if result.get("success") else "failed",
            "parsed_at": datetime.now(timezone.utc) if result.get("success") else None,
            "entries_found": len(result.get("job_entries", [])),
            "signals_fired": len(result.get("signals", [])),
            "error": result.get("error"),
            "source": "upload",
        }

        logger.info(
            "cv.upload.finished_sync",
            job_id=str(job_id),
            user_id=str(user_id),
            success=result.get("success"),
        )
    else:
        # Mark as queued when published to Kafka
        _job_store[job_id] = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "queued",
            "parsed_at": None,
            "entries_found": 0,
            "signals_fired": 0,
            "error": None,
            "source": "upload",
        }

    return CVUploadResponse(
        job_id=job_id,
        user_id=user_id,
        status="queued",
        message="CV processing has been queued",
    )


@router.post(
    "/users/{user_id}/cv/text",
    response_model=CVUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Paste raw CV text",
    description="Submit raw CV text for parsing. Returns a job ID for status polling.",
)
async def upload_cv_text(
    user_id: UUID,
    payload: CVTextRequest,
    _current_user: User = Depends(get_current_user),
    kafka_producer: KafkaProducerService | None = Depends(get_kafka_producer),
) -> CVUploadResponse:
    """Accept pasted CV text and queue or parse it.

    If a Kafka producer is available the raw text is published to
    ``raw.cv.uploads`` and a 202 is returned immediately.  Otherwise the
    endpoint falls back to synchronous in-process parsing.

    Args:
        user_id: Target user ID from the path.
        payload: Request body containing raw_text and source.
        kafka_producer: Optional Kafka producer injected by FastAPI.

    Returns:
        CVUploadResponse with a job_id for status polling.
    """
    job_id = uuid4()

    logger.info(
        "cv.text.started",
        job_id=str(job_id),
        user_id=str(user_id),
        text_length=len(payload.raw_text),
    )

    # --- Kafka path ---
    published = False
    if kafka_producer is not None:
        try:
            message = CVUploadMessage(
                user_id=str(user_id),
                source="paste",
                s3_key="",  # No file uploaded — raw text only
                raw_text=payload.raw_text,
                filename="paste.txt",
                event_id=str(job_id),
            )
            await kafka_producer.send(
                topic=KafkaTopic.RAW_CV_UPLOADS.value,
                message=message.to_dict(),
                key=str(user_id),
            )
            published = True
            logger.info(
                "cv.text.published_to_kafka",
                job_id=str(job_id),
                user_id=str(user_id),
                topic=KafkaTopic.RAW_CV_UPLOADS.value,
            )
        except Exception:
            logger.warning(
                "cv.text.kafka_publish_failed",
                job_id=str(job_id),
                user_id=str(user_id),
                exc_info=True,
            )

    # --- Synchronous fallback ---
    if not published:
        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=True, encoding="utf-8"
        ) as tmp:
            tmp.write(payload.raw_text)
            tmp.flush()

            result = await parse_cv(file_path=tmp.name, user_id=user_id)

        _job_store[job_id] = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "completed" if result.get("success") else "failed",
            "parsed_at": datetime.now(timezone.utc) if result.get("success") else None,
            "entries_found": len(result.get("job_entries", [])),
            "signals_fired": len(result.get("signals", [])),
            "error": result.get("error"),
            "source": "paste",
        }

        logger.info(
            "cv.text.finished_sync",
            job_id=str(job_id),
            user_id=str(user_id),
            success=result.get("success"),
        )
    else:
        _job_store[job_id] = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "queued",
            "parsed_at": None,
            "entries_found": 0,
            "signals_fired": 0,
            "error": None,
            "source": "paste",
        }

    return CVUploadResponse(
        job_id=job_id,
        user_id=user_id,
        status="queued",
        message="CV text processing has been queued",
    )


@router.get(
    "/users/{user_id}/cv/status/{job_id}",
    response_model=CVStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check CV parse job status",
    description="Poll the status of a CV parsing job by its job_id.",
)
async def get_cv_status(
    user_id: UUID,
    job_id: UUID,
    _current_user: User = Depends(get_current_user),
) -> CVStatusResponse:
    """Return the current status of a CV parsing job.

    Args:
        user_id: Owner user ID from the path.
        job_id: Job ID returned by the upload/text endpoint.

    Returns:
        CVStatusResponse with current status and results.

    Raises:
        HTTPException 404: If the job_id is not found.
    """
    job = _job_store.get(job_id)

    if job is None or job.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found for user {user_id}",
        )

    return CVStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        parsed_at=job.get("parsed_at"),
        entries_found=job.get("entries_found"),
        signals_fired=job.get("signals_fired"),
        error=job.get("error"),
    )
