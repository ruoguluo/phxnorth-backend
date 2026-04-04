"""Pydantic schemas for admin endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Signal source filter
# ---------------------------------------------------------------------------


class SignalSource(str, Enum):
    """Allowed values for the signal source query parameter."""

    CV = "cv"
    PLATFORM = "platform"
    ALL = "all"


# ---------------------------------------------------------------------------
# Signal schemas
# ---------------------------------------------------------------------------


class SignalItem(BaseModel):
    """A single behavioral signal."""

    signal_id: str = Field(description="Unique identifier for the signal.")
    signal_type: str = Field(description="Type of signal (e.g. 'response_time', 'keyword').")
    source: str = Field(description="Signal source: 'cv' or 'platform'.")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score for this signal (0–1).",
    )
    timestamp: datetime = Field(description="When the signal was recorded (ISO-8601).")
    evidence: str = Field(description="Supporting evidence or context for the signal.")


class UserSignalsResponse(BaseModel):
    """Response for GET /admin/users/{user_id}/signals."""

    user_id: UUID = Field(description="ID of the user whose signals are returned.")
    signals: list[SignalItem] = Field(
        default_factory=list,
        description="List of behavioral signals.",
    )


# ---------------------------------------------------------------------------
# DISC recompute schemas
# ---------------------------------------------------------------------------


class DISCRecomputeResponse(BaseModel):
    """Response for POST /admin/users/{user_id}/disc/recompute."""

    job_id: str = Field(description="Unique identifier for the queued recompute job.")
    status: str = Field(description="Job status (e.g. 'queued').")
    message: str = Field(description="Human-readable status message.")


# ---------------------------------------------------------------------------
# Red flag severity filter
# ---------------------------------------------------------------------------


class RedFlagSeverity(str, Enum):
    """Allowed values for the red flag severity query parameter."""

    RED = "red"
    ORANGE = "orange"


# ---------------------------------------------------------------------------
# Red flag schemas
# ---------------------------------------------------------------------------


class RedFlagItem(BaseModel):
    """A single red flag entry."""

    id: str = Field(description="Unique identifier for this red flag.")
    user_id: UUID = Field(description="ID of the user associated with the flag.")
    flag_type: str = Field(description="Type of red flag (e.g. 'contradiction', 'anomaly').")
    severity: str = Field(description="Severity level: 'red' or 'orange'.")
    description: str = Field(description="Human-readable description of the flag.")
    created_at: datetime = Field(description="When the flag was created (ISO-8601).")
    resolved: bool = Field(description="Whether the flag has been resolved.")


class RedFlagListResponse(BaseModel):
    """Response for GET /admin/red-flags."""

    total: int = Field(ge=0, description="Total number of matching flags.")
    flags: list[RedFlagItem] = Field(
        default_factory=list,
        description="List of red flag entries.",
    )
