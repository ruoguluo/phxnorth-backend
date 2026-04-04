"""Pydantic schemas for behavioral event ingestion endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    """Schema for a single incoming behavioral event.

    The ``event_id`` is optional – the server will generate one if omitted.
    ``timestamp`` is mapped to the internal ``created_at`` field expected by
    the event validator.
    """

    event_id: UUID | None = Field(
        default=None,
        description="Client-supplied event ID (UUID v4). Generated server-side if omitted.",
    )
    user_id: UUID = Field(
        ...,
        description="ID of the user who produced the event.",
    )
    session_id: UUID | None = Field(
        default=None,
        description="Session in which the event occurred.",
    )
    event_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Type of behavioral event (e.g. MESSAGE_RESPONDED).",
    )
    timestamp: datetime = Field(
        ...,
        description="When the event occurred (ISO-8601).",
    )
    latency_ms: int | None = Field(
        default=None,
        ge=0,
        description="Latency in milliseconds, if applicable.",
    )
    client_type: str | None = Field(
        default=None,
        description="Client platform (web, mobile, api, desktop).",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary event-specific data.",
    )

    def to_validator_dict(self) -> dict[str, Any]:
        """Convert to the dict shape expected by ``validate_event()``."""
        d: dict[str, Any] = {
            "user_id": str(self.user_id),
            "event_type": self.event_type,
            "created_at": self.timestamp.isoformat(),
            "payload": self.payload,
        }
        if self.session_id is not None:
            d["session_id"] = str(self.session_id)
        if self.latency_ms is not None:
            d["latency_ms"] = self.latency_ms
        if self.client_type is not None:
            d["client_type"] = self.client_type
        return d


class BatchEventsIn(BaseModel):
    """Schema for batch event ingestion (max 100 events)."""

    events: list[EventIn] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of events to ingest (1–100).",
    )


class RejectedEventDetail(BaseModel):
    """Details about a single rejected event."""

    index: int = Field(description="Zero-based index in the submitted batch.")
    event_id: str | None = Field(description="Client-supplied event_id, if any.")
    errors: list[str] = Field(description="Validation error messages.")


class EventIngestionResponse(BaseModel):
    """Response returned after ingesting events."""

    accepted: int = Field(description="Number of events accepted.")
    rejected: int = Field(description="Number of events rejected.")
    event_ids: list[str] = Field(
        default_factory=list,
        description="IDs of accepted events.",
    )
    rejected_details: list[RejectedEventDetail] = Field(
        default_factory=list,
        description="Details for each rejected event (batch only).",
    )
