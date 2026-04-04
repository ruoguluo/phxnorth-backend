"""Pydantic schemas for career profile and preference index endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Career profile schemas
# ---------------------------------------------------------------------------


class JobEntry(BaseModel):
    """A single job entry from the parsed CV / career history."""

    title: str = Field(description="Job title.")
    company: str = Field(description="Company or organisation name.")
    start_date: str | None = Field(
        default=None,
        description="Start date (ISO-8601 or free-text).",
    )
    end_date: str | None = Field(
        default=None,
        description="End date (ISO-8601, free-text, or null if current).",
    )
    duration_months: int | None = Field(
        default=None,
        ge=0,
        description="Duration in months.",
    )


class TurningPoint(BaseModel):
    """A detected career turning-point or inflection event."""

    date: str | None = Field(
        default=None,
        description="Approximate date of the turning point.",
    )
    description: str = Field(description="Human-readable description.")
    type: str = Field(
        description="Category of turning point (e.g. promotion, pivot, exit).",
    )


class CareerAnalytics(BaseModel):
    """Aggregate analytics derived from the career profile."""

    total_experience_months: int = Field(
        default=0,
        ge=0,
        description="Total career experience in months.",
    )
    avg_tenure_months: float = Field(
        default=0.0,
        ge=0.0,
        description="Average tenure per role in months.",
    )
    distinct_companies: int = Field(
        default=0,
        ge=0,
        description="Number of distinct employers.",
    )
    distinct_roles: int = Field(
        default=0,
        ge=0,
        description="Number of distinct job titles.",
    )


class CareerProfileResponse(BaseModel):
    """Response for GET /users/{user_id}/career."""

    user_id: UUID = Field(description="User ID.")
    analytics: CareerAnalytics = Field(
        description="Aggregate career analytics.",
    )
    job_entries: list[JobEntry] = Field(
        default_factory=list,
        description="Ordered list of job entries.",
    )
    turning_points: list[TurningPoint] = Field(
        default_factory=list,
        description="Detected career turning points.",
    )


# ---------------------------------------------------------------------------
# Preference index schemas
# ---------------------------------------------------------------------------


class PreferenceIndexValue(BaseModel):
    """A single preference index with its value, label, and interpretation."""

    value: float = Field(
        description="Numeric index value (range depends on the specific index).",
    )
    label: str = Field(
        description="Human-readable label summarising the value.",
    )
    interpretation: str = Field(
        description="Longer interpretive explanation of the value.",
    )


class PreferenceIndexes(BaseModel):
    """Container for all computed preference indexes."""

    stability_vs_growth: PreferenceIndexValue = Field(
        description=(
            "Stability vs Growth orientation. "
            "Range -1 (stability) to 1 (growth)."
        ),
    )
    conservative_vs_aggressive_risk: PreferenceIndexValue = Field(
        description="Conservative vs Aggressive risk appetite.",
    )
    control_vs_collaboration: PreferenceIndexValue = Field(
        description="Control vs Collaboration leadership style.",
    )
    short_term_vs_long_term: PreferenceIndexValue = Field(
        description="Short-term vs Long-term planning horizon.",
    )
    consistency_score: PreferenceIndexValue = Field(
        description="Consistency score (0–1).",
    )


class PreferencesResponse(BaseModel):
    """Response for GET /users/{user_id}/preferences."""

    user_id: UUID = Field(description="User ID.")
    computed_at: datetime = Field(
        description="Timestamp when the indexes were computed.",
    )
    indexes: PreferenceIndexes = Field(
        description="Computed preference indexes.",
    )
