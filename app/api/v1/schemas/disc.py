"""Pydantic schemas for DISC profile query endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class WindowParam(str, Enum):
    """Supported DISC profile analysis windows."""

    DAYS_30 = "30d"
    DAYS_90 = "90d"
    LIFETIME = "lifetime"


class DISCScores(BaseModel):
    """DISC dimension scores (0–100)."""

    D: float = Field(..., ge=0, le=100, description="Dominance score")
    I: float = Field(..., ge=0, le=100, description="Influence score")
    S: float = Field(..., ge=0, le=100, description="Steadiness score")
    C: float = Field(..., ge=0, le=100, description="Conscientiousness score")


class DISCProfileResponse(BaseModel):
    """Response schema for GET /users/{user_id}/disc-profile."""

    user_id: UUID
    window: str = Field(
        ...,
        description="Analysis window used (30d, 90d, or lifetime).",
    )
    computed_at: datetime = Field(
        ...,
        description="Timestamp when the profile was computed.",
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence score (0.000–1.000).",
    )
    scores: DISCScores
    dominant: str | None = Field(
        None,
        description="Primary DISC trait (D, I, S, or C).",
    )
    secondary: str | None = Field(
        None,
        description="Secondary DISC trait.",
    )
    data_sources: int = Field(
        ...,
        ge=0,
        description="Number of behavioral signals used to compute the profile.",
    )


class DISCHistoryEntry(BaseModel):
    """A single entry in the DISC profile history timeline."""

    computed_at: datetime
    scores: DISCScores
    dominant: str | None = None


class DISCProfileHistoryResponse(BaseModel):
    """Response schema for GET /users/{user_id}/disc-profile/history."""

    user_id: UUID
    history: list[DISCHistoryEntry] = Field(
        default_factory=list,
        description="Chronologically ordered profile snapshots.",
    )
