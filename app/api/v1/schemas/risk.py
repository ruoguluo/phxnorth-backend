"""Pydantic schemas for risk assessment and contradiction analysis endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Risk assessment schemas
# ---------------------------------------------------------------------------


class RiskAssessmentItem(BaseModel):
    """A single risk assessment entry."""

    category: str = Field(description="Risk category (e.g. 'attrition', 'disengagement').")
    score: float = Field(ge=0.0, le=1.0, description="Risk score between 0 and 1.")
    severity: str = Field(description="Severity tier: low, medium, high, critical.")
    description: str = Field(description="Human-readable explanation of the risk.")


class RiskFlag(BaseModel):
    """An active risk flag raised by the system."""

    flag_id: str = Field(description="Unique identifier for this flag.")
    category: str = Field(description="Risk category this flag belongs to.")
    raised_at: datetime = Field(description="When the flag was raised (ISO-8601).")
    message: str = Field(description="Human-readable flag description.")


class RiskAssessmentResponse(BaseModel):
    """Response for GET /users/{user_id}/risk."""

    user_id: UUID = Field(description="ID of the assessed user.")
    computed_at: datetime = Field(description="When the assessment was computed.")
    overall_risk_tier: str = Field(description="Overall risk tier: low, medium, high, critical.")
    assessments: list[RiskAssessmentItem] = Field(
        default_factory=list,
        description="Per-category risk assessments.",
    )
    active_flags: list[RiskFlag] = Field(
        default_factory=list,
        description="Currently active risk flags.",
    )


# ---------------------------------------------------------------------------
# Risk history schemas
# ---------------------------------------------------------------------------


class RiskHistoryEntry(BaseModel):
    """A single point in the risk history timeline."""

    computed_at: datetime = Field(description="When this score was computed.")
    score: float = Field(ge=0.0, le=1.0, description="Risk score at this point in time.")
    severity: str = Field(description="Severity tier at this point in time.")


class RiskHistoryResponse(BaseModel):
    """Response for GET /users/{user_id}/risk/history."""

    user_id: UUID = Field(description="ID of the user.")
    category: str | None = Field(
        default=None,
        description="Risk category filter applied (null = all categories).",
    )
    history: list[RiskHistoryEntry] = Field(
        default_factory=list,
        description="Chronological risk history entries.",
    )


# ---------------------------------------------------------------------------
# Contradiction analysis schemas
# ---------------------------------------------------------------------------


class DimensionGap(BaseModel):
    """A gap detected between two DISC dimensions."""

    dimension_a: str = Field(description="First DISC dimension.")
    dimension_b: str = Field(description="Second DISC dimension.")
    gap: float = Field(description="Magnitude of the gap between dimensions.")
    interpretation: str = Field(description="What this gap may indicate.")


class ContradictionResponse(BaseModel):
    """Response for GET /users/{user_id}/contradiction."""

    user_id: UUID = Field(description="ID of the analysed user.")
    contradiction_score: float = Field(
        ge=0.0, le=1.0,
        description="Overall contradiction score (0 = consistent, 1 = highly contradictory).",
    )
    severity_tier: str = Field(description="Severity tier: none, low, medium, high.")
    threshold_exceeded: bool = Field(
        description="Whether the contradiction score exceeds the configured threshold.",
    )
    dimension_gaps: list[DimensionGap] = Field(
        default_factory=list,
        description="Detected gaps between DISC dimensions.",
    )
    flagged_dimensions: list[str] = Field(
        default_factory=list,
        description="DISC dimensions flagged for inconsistency.",
    )
    contradiction_type: str | None = Field(
        default=None,
        description="Classification of the contradiction pattern (e.g. 'self-report vs behavioral').",
    )


# ---------------------------------------------------------------------------
# Behavioral shift schemas
# ---------------------------------------------------------------------------


class BehavioralShiftResponse(BaseModel):
    """Response for GET /users/{user_id}/behavioral-shift."""

    user_id: UUID = Field(description="ID of the user.")
    shift_detected: bool = Field(description="Whether a significant behavioral shift was detected.")
    magnitude: float = Field(
        ge=0.0, le=1.0,
        description="Magnitude of the shift (0 = no shift, 1 = maximum shift).",
    )
    shift_type: str | None = Field(
        default=None,
        description="Type of shift detected (e.g. 'gradual', 'sudden', 'oscillating').",
    )
    shifted_dimensions: list[str] = Field(
        default_factory=list,
        description="DISC dimensions that shifted.",
    )
    interpretation: str | None = Field(
        default=None,
        description="Human-readable interpretation of the shift.",
    )
