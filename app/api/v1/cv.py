"""CV upload and parsing endpoints."""

from __future__ import annotations

import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_kafka_producer
from app.api.v1.schemas.cv import CVStatusResponse, CVTextRequest, CVUploadResponse
from app.kafka.schemas import CVUploadMessage
from app.kafka.topics import KafkaTopic
from app.models.career import (
    CareerAnalytics as CareerAnalyticsModel,
    CareerProfile,
    JobEntry,
    ProfileSource,
)
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


def _parse_date(value: str | date | None) -> date | None:
    """Convert a date string (YYYY-MM-DD) or date object to a date, or None."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


async def _persist_parse_result(
    db: AsyncSession,
    user_id: UUID,
    source: str,
    result: dict[str, Any],
) -> None:
    """Store parsed CV data in career_profiles, job_entries, and career_analytics.

    Deletes any existing career data for the user before inserting, so that
    re-uploading a CV replaces old data.
    """
    now = datetime.now(timezone.utc)

    # --- Clean up existing data for this user ---
    await db.execute(delete(JobEntry).where(JobEntry.user_id == user_id))
    await db.execute(delete(CareerProfile).where(CareerProfile.user_id == user_id))
    await db.execute(
        delete(CareerAnalyticsModel).where(CareerAnalyticsModel.user_id == user_id)
    )

    # --- CareerProfile ---
    profile_source = ProfileSource.UPLOAD if source == "upload" else ProfileSource.PASTE
    profile = CareerProfile(
        user_id=user_id,
        source=profile_source,
        raw_text=result.get("raw_text"),
        parsed_at=now,
        parser_version=result.get("parser_version"),
    )
    db.add(profile)
    await db.flush()  # Populate profile.id for FK references

    # --- JobEntries ---
    for idx, entry in enumerate(result.get("job_entries", [])):
        start = _parse_date(entry.get("start_date"))
        if start is None:
            # start_date is required — skip entries without one
            logger.warning(
                "cv.persist.skipping_job_entry",
                reason="missing_start_date",
                index=idx,
                company=entry.get("company_name"),
            )
            continue

        job = JobEntry(
            career_profile_id=profile.id,
            user_id=user_id,
            company_name=entry.get("company_name"),
            job_title=entry.get("job_title"),
            start_date=start,
            end_date=_parse_date(entry.get("end_date")),
            duration_months=entry.get("duration_months"),
            description_raw=entry.get("description"),
            sequence_index=idx,
        )
        db.add(job)

    # --- CareerAnalytics ---
    analytics = result.get("analytics") or {}
    metrics = analytics.get("metrics") or {}
    if metrics:
        analytics_record = CareerAnalyticsModel(
            user_id=user_id,
            total_roles=metrics.get("total_roles"),
            short_tenure_count=metrics.get("short_tenure_count"),
            short_tenure_rate=metrics.get("short_tenure_rate"),
            avg_tenure_months=metrics.get("avg_tenure_months"),
            career_span_years=metrics.get("career_span_years"),
            transition_frequency=metrics.get("transition_frequency"),
            cross_industry_transitions=metrics.get("cross_industry_transitions"),
            upward_moves=metrics.get("upward_moves"),
            lateral_moves=metrics.get("lateral_moves"),
            downward_moves=metrics.get("downward_moves"),
            industry_diversity_score=metrics.get("industry_diversity_score"),
            functional_diversity_score=metrics.get("functional_diversity_score"),
            longest_tenure_months=metrics.get("longest_tenure_months"),
            career_volatility_score=metrics.get("career_volatility_score"),
            computed_at=now,
        )
        db.add(analytics_record)

    await db.commit()

    logger.info(
        "cv.persist.completed",
        user_id=str(user_id),
        profile_id=str(profile.id),
        job_entries_saved=len(result.get("job_entries", [])),
        has_analytics=bool(metrics),
    )


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
    db: AsyncSession = Depends(get_db),
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

    # --- Always parse synchronously for immediate results ---
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(contents)
        tmp.flush()

        result = await parse_cv(file_path=tmp.name, user_id=user_id)

    parse_success = result.get("success", False)

    _job_store[job_id] = {
        "job_id": job_id,
        "user_id": user_id,
        "status": "completed" if parse_success else "failed",
        "parsed_at": datetime.now(timezone.utc) if parse_success else None,
        "entries_found": len(result.get("job_entries", [])),
        "signals_fired": len(result.get("signals", [])),
        "error": result.get("error"),
        "source": "upload",
    }

    # Persist to database if parsing succeeded
    if parse_success:
        try:
            await _persist_parse_result(db, user_id, "upload", result)
        except Exception:
            logger.exception(
                "cv.upload.persist_failed",
                job_id=str(job_id),
                user_id=str(user_id),
            )

    logger.info(
        "cv.upload.finished",
        job_id=str(job_id),
        user_id=str(user_id),
        success=parse_success,
        entries_found=len(result.get("job_entries", [])),
    )

    return CVUploadResponse(
        job_id=job_id,
        user_id=user_id,
        status="completed" if parse_success else "failed",
        message="CV parsed successfully" if parse_success else f"CV parsing failed: {result.get('error', 'unknown')}",
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
    db: AsyncSession = Depends(get_db),
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

    # --- Always parse synchronously for immediate results ---
    with tempfile.NamedTemporaryFile(
        suffix=".txt", mode="w", delete=True, encoding="utf-8"
    ) as tmp:
        tmp.write(payload.raw_text)
        tmp.flush()

        result = await parse_cv(file_path=tmp.name, user_id=user_id)

    parse_success = result.get("success", False)

    _job_store[job_id] = {
        "job_id": job_id,
        "user_id": user_id,
        "status": "completed" if parse_success else "failed",
        "parsed_at": datetime.now(timezone.utc) if parse_success else None,
        "entries_found": len(result.get("job_entries", [])),
        "signals_fired": len(result.get("signals", [])),
        "error": result.get("error"),
        "source": "paste",
    }

    # Persist to database if parsing succeeded
    if parse_success:
        try:
            await _persist_parse_result(db, user_id, "paste", result)
        except Exception:
            logger.exception(
                "cv.text.persist_failed",
                job_id=str(job_id),
                user_id=str(user_id),
            )

    logger.info(
        "cv.text.finished",
        job_id=str(job_id),
        user_id=str(user_id),
        success=parse_success,
        entries_found=len(result.get("job_entries", [])),
    )

    return CVUploadResponse(
        job_id=job_id,
        user_id=user_id,
        status="completed" if parse_success else "failed",
        message="CV parsed successfully" if parse_success else f"CV parsing failed: {result.get('error', 'unknown')}",
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


@router.get(
    "/users/{user_id}/cv/latest",
    status_code=status.HTTP_200_OK,
    summary="Get the latest uploaded CV",
    description="Returns metadata and raw text of the most recently uploaded CV for a user.",
)
async def get_latest_cv(
    user_id: UUID,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the latest CV for the given user.

    Args:
        user_id: Owner user ID from the path.

    Returns:
        Dict with CV metadata and raw text content.

    Raises:
        HTTPException 404: If no CV has been uploaded for this user.
    """
    result = await db.execute(
        select(CareerProfile)
        .where(CareerProfile.user_id == user_id)
        .order_by(CareerProfile.created_at.desc())
        .limit(1)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CV found for this user",
        )

    raw_text = profile.raw_text or ""

    return {
        "id": str(profile.id),
        "user_id": str(profile.user_id),
        "source": profile.source,
        "parsed_at": profile.parsed_at.isoformat() if profile.parsed_at else None,
        "parser_version": profile.parser_version,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "word_count": len(raw_text.split()),
        "char_count": len(raw_text),
        "raw_text": raw_text,
    }
