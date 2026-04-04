"""Behavioral event ingestion endpoints.

Provides single-event and batch ingestion for behavioral events that feed
into the DISC signal extraction pipeline.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, status

from app.api.deps import get_deduplicator, get_kafka_producer
from app.api.v1.schemas.events import (
    BatchEventsIn,
    EventIn,
    EventIngestionResponse,
    RejectedEventDetail,
)
from app.kafka.schemas import BehavioralEventMessage
from app.kafka.topics import KafkaTopic
from app.services.signal_extractor.validation.event_validator import validate_event

if TYPE_CHECKING:
    from app.cache.dedup import EventDeduplicator
    from app.kafka.producer import KafkaProducerService

logger = structlog.get_logger(__name__)

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

    logger.info(
        "event_accepted",
        event_id=event_id,
        event_type=event.event_type,
        user_id=str(event.user_id),
    )
    return event_id, None


async def _publish_events_to_kafka(
    producer: KafkaProducerService | None,
    events: list[EventIn],
    event_ids: list[str],
) -> None:
    """Best-effort publish of validated events to Kafka.

    If the producer is ``None`` or sending fails, the events are silently
    accepted (they were already validated).  A warning is logged on failure
    so operators can detect Kafka issues.
    """
    if producer is None or not events:
        return

    messages = []
    for event, eid in zip(events, event_ids):
        msg = BehavioralEventMessage(
            user_id=str(event.user_id),
            session_id=str(event.session_id) if event.session_id else "",
            event_type=event.event_type,
            payload=event.payload,
            latency_ms=event.latency_ms,
            client_type=event.client_type,
            event_id=eid,
        )
        messages.append(msg.to_dict())

    try:
        await producer.send_batch(
            topic=KafkaTopic.RAW_BEHAVIORAL_EVENTS.value,
            messages=messages,
        )
        logger.info(
            "events_published_to_kafka",
            count=len(messages),
            topic=KafkaTopic.RAW_BEHAVIORAL_EVENTS.value,
        )
    except Exception:
        logger.warning(
            "events_kafka_publish_failed",
            count=len(messages),
            topic=KafkaTopic.RAW_BEHAVIORAL_EVENTS.value,
            exc_info=True,
        )


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
    kafka_producer: KafkaProducerService | None = Depends(get_kafka_producer),
    deduplicator: EventDeduplicator | None = Depends(get_deduplicator),
) -> EventIngestionResponse:
    """Ingest a single behavioral event.

    If a deduplicator is available, duplicate event IDs are rejected.
    If a Kafka producer is available the validated event is published to
    ``raw.behavioral.events``.  Otherwise the event is accepted
    synchronously (logged only until downstream persistence is wired).
    """
    event_id, rejected = _process_single_event(event)

    if rejected is not None:
        return EventIngestionResponse(
            accepted=0,
            rejected=1,
            event_ids=[],
            rejected_details=[rejected],
        )

    # --- Deduplication ---
    if deduplicator is not None and event_id is not None:
        try:
            is_new = await deduplicator.check_and_mark(event_id)
            if not is_new:
                logger.info("event_duplicate_rejected", event_id=event_id)
                return EventIngestionResponse(
                    accepted=0,
                    rejected=1,
                    event_ids=[],
                    rejected_details=[
                        RejectedEventDetail(
                            index=0,
                            event_id=event_id,
                            errors=["Duplicate event_id"],
                        ),
                    ],
                )
        except Exception:
            logger.warning(
                "dedup_check_failed", event_id=event_id, exc_info=True
            )

    # Publish to Kafka (best-effort; fall back to sync acceptance)
    await _publish_events_to_kafka(kafka_producer, [event], [event_id])  # type: ignore[arg-type]

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
    kafka_producer: KafkaProducerService | None = Depends(get_kafka_producer),
    deduplicator: EventDeduplicator | None = Depends(get_deduplicator),
) -> EventIngestionResponse:
    """Ingest a batch of behavioral events (max 100).

    Validated events are checked for duplicates (when Redis is available)
    and published to Kafka when a producer is available, otherwise they
    are accepted synchronously.
    """
    accepted_ids: list[str] = []
    accepted_events: list[EventIn] = []
    rejected_details: list[RejectedEventDetail] = []

    for idx, event in enumerate(body.events):
        event_id, rejected = _process_single_event(event, index=idx)
        if rejected is not None:
            rejected_details.append(rejected)
            continue

        # --- Deduplication ---
        if deduplicator is not None and event_id is not None:
            try:
                is_new = await deduplicator.check_and_mark(event_id)
                if not is_new:
                    logger.info(
                        "batch_event_duplicate_rejected",
                        event_id=event_id,
                        index=idx,
                    )
                    rejected_details.append(
                        RejectedEventDetail(
                            index=idx,
                            event_id=event_id,
                            errors=["Duplicate event_id"],
                        ),
                    )
                    continue
            except Exception:
                logger.warning(
                    "dedup_check_failed",
                    event_id=event_id,
                    index=idx,
                    exc_info=True,
                )

        accepted_ids.append(event_id)  # type: ignore[arg-type]
        accepted_events.append(event)

    # Publish accepted events to Kafka
    await _publish_events_to_kafka(kafka_producer, accepted_events, accepted_ids)

    logger.info(
        "batch_ingestion_complete",
        accepted=len(accepted_ids),
        rejected=len(rejected_details),
    )

    return EventIngestionResponse(
        accepted=len(accepted_ids),
        rejected=len(rejected_details),
        event_ids=accepted_ids,
        rejected_details=rejected_details,
    )
