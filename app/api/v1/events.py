"""Behavioral event ingestion endpoints.

Provides single-event and batch ingestion for behavioral events that feed
into the DISC signal extraction pipeline.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, status

from app.api.v1.schemas.events import (
    BatchEventsIn,
    EventIn,
    EventIngestionResponse,
    RejectedEventDetail,
)
from app.services.signal_extractor.validation.event_validator import validate_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


# ---------------------------------------------------------------------------
# Placeholder auth dependency
# ---------------------------------------------------------------------------

async def _require_auth() -> dict[str, Any]:
    """Placeholder authentication dependency.

    In a future phase this will verify a JWT bearer token and return the
    decoded claims.  For now it returns a stub user so that downstream code
    can reference ``current_user["sub"]`` without changes.
    """
    # TODO: Replace with real JWT verification (Phase 6 – Auth endpoints)
    return {"sub": "placeholder-user", "role": "user"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _process_single_event(
    event: EventIn,
    index: int = 0,
) -> tuple[str | None, RejectedEventDetail | None]:
    """Validate and accept/reject a single event.

    Returns:
        A tuple of (event_id, None) on success, or (None, detail) on failure.
    """
    event_id = str(event.event_id) if event.event_id else str(uuid.uuid4())
    raw = event.to_validator_dict()
    result = validate_event(raw)

    if not result["valid"]:
        return None, RejectedEventDetail(
            index=index,
            event_id=str(event.event_id) if event.event_id else None,
            errors=result["errors"],
        )

    # TODO: Persist event / publish to Kafka (Phase 7)
    logger.info(
        "Accepted event %s (type=%s, user=%s)",
        event_id,
        event.event_type,
        event.user_id,
    )
    return event_id, None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=EventIngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a single behavioral event",
    description=(
        "Validates and accepts a single behavioral event for processing. "
        "Returns 202 on success with the accepted event ID."
    ),
)
async def ingest_event(
    event: EventIn,
    current_user: dict[str, Any] = Depends(_require_auth),
) -> EventIngestionResponse:
    """Ingest a single behavioral event."""
    event_id, rejected = _process_single_event(event)

    if rejected is not None:
        return EventIngestionResponse(
            accepted=0,
            rejected=1,
            event_ids=[],
            rejected_details=[rejected],
        )

    return EventIngestionResponse(
        accepted=1,
        rejected=0,
        event_ids=[event_id],  # type: ignore[list-item]
    )


@router.post(
    "/batch",
    response_model=EventIngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of behavioral events",
    description=(
        "Validates and accepts up to 100 behavioral events in a single "
        "request. Returns per-event acceptance/rejection details."
    ),
)
async def ingest_batch(
    body: BatchEventsIn,
    current_user: dict[str, Any] = Depends(_require_auth),
) -> EventIngestionResponse:
    """Ingest a batch of behavioral events (max 100)."""
    accepted_ids: list[str] = []
    rejected_details: list[RejectedEventDetail] = []

    for idx, event in enumerate(body.events):
        event_id, rejected = _process_single_event(event, index=idx)
        if rejected is not None:
            rejected_details.append(rejected)
        else:
            accepted_ids.append(event_id)  # type: ignore[arg-type]

    logger.info(
        "Batch ingestion complete: %d accepted, %d rejected",
        len(accepted_ids),
        len(rejected_details),
    )

    return EventIngestionResponse(
        accepted=len(accepted_ids),
        rejected=len(rejected_details),
        event_ids=accepted_ids,
        rejected_details=rejected_details,
    )
