"""Risk assessment, contradiction analysis, and behavioral shift endpoints.

Provides placeholder endpoints that return structured responses matching the
API spec.  Real computation will be wired in once the scoring pipeline is
integrated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.api.v1.schemas.risk import (
    BehavioralShiftResponse,
    ContradictionResponse,
    DimensionGap,
    RiskAssessmentItem,
    RiskAssessmentResponse,
    RiskFlag,
    RiskHistoryEntry,
    RiskHistoryResponse,
)

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(tags=["risk"])


# ---------------------------------------------------------------------------
# GET /users/{user_id}/risk
# ---------------------------------------------------------------------------


@router.get(
    "/users/{user_id}/risk",
    response_model=RiskAssessmentResponse,
    summary="Get risk assessments for a user",
    description=(
        "Returns the current risk assessment for a user, including "
        "per-category scores and any active risk flags."
    ),
)
async def get_risk_assessment(
    user_id: UUID,
    _current_user: User = Depends(get_current_user),
) -> RiskAssessmentResponse:
    """Return placeholder risk assessment for the given user."""
    now = datetime.now(timezone.utc)

    return RiskAssessmentResponse(
        user_id=user_id,
        computed_at=now,
        overall_risk_tier="low",
        assessments=[
            RiskAssessmentItem(
                category="attrition",
                score=0.15,
                severity="low",
                description="No significant attrition signals detected.",
            ),
            RiskAssessmentItem(
                category="disengagement",
                score=0.10,
                severity="low",
                description="Engagement levels appear stable.",
            ),
        ],
        active_flags=[
            RiskFlag(
                flag_id="flag-placeholder-001",
                category="attrition",
                raised_at=now,
                message="Placeholder flag — no real risk data available yet.",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# GET /users/{user_id}/risk/history
# ---------------------------------------------------------------------------


@router.get(
    "/users/{user_id}/risk/history",
    response_model=RiskHistoryResponse,
    summary="Get risk history for a user",
    description=(
        "Returns historical risk scores for a user, optionally filtered by "
        "category and date range."
    ),
)
async def get_risk_history(
    user_id: UUID,
    category: str | None = Query(
        default=None,
        description="Risk category to filter by (e.g. 'attrition').",
    ),
    from_date: datetime | None = Query(
        default=None,
        alias="from",
        description="Start of date range (ISO-8601).",
    ),
    to_date: datetime | None = Query(
        default=None,
        alias="to",
        description="End of date range (ISO-8601).",
    ),
    _current_user: User = Depends(get_current_user),
) -> RiskHistoryResponse:
    """Return placeholder risk history for the given user."""
    now = datetime.now(timezone.utc)

    return RiskHistoryResponse(
        user_id=user_id,
        category=category,
        history=[
            RiskHistoryEntry(
                computed_at=now,
                score=0.15,
                severity="low",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# GET /users/{user_id}/contradiction
# ---------------------------------------------------------------------------


@router.get(
    "/users/{user_id}/contradiction",
    response_model=ContradictionResponse,
    summary="Get contradiction analysis for a user",
    description=(
        "Analyses the user's DISC profile for internal contradictions and "
        "returns dimension gaps, flagged dimensions, and severity."
    ),
)
async def get_contradiction_analysis(
    user_id: UUID,
    _current_user: User = Depends(get_current_user),
) -> ContradictionResponse:
    """Return placeholder contradiction analysis for the given user."""
    return ContradictionResponse(
        user_id=user_id,
        contradiction_score=0.12,
        severity_tier="low",
        threshold_exceeded=False,
        dimension_gaps=[
            DimensionGap(
                dimension_a="D",
                dimension_b="S",
                gap=0.08,
                interpretation="Minimal gap between Dominance and Steadiness.",
            ),
        ],
        flagged_dimensions=[],
        contradiction_type=None,
    )


# ---------------------------------------------------------------------------
# GET /users/{user_id}/behavioral-shift
# ---------------------------------------------------------------------------


@router.get(
    "/users/{user_id}/behavioral-shift",
    response_model=BehavioralShiftResponse,
    summary="Detect behavioral shifts for a user",
    description=(
        "Analyses the user's behavioral history for significant shifts in "
        "DISC dimensions over time."
    ),
)
async def get_behavioral_shift(
    user_id: UUID,
    _current_user: User = Depends(get_current_user),
) -> BehavioralShiftResponse:
    """Return placeholder behavioral shift analysis for the given user."""
    return BehavioralShiftResponse(
        user_id=user_id,
        shift_detected=False,
        magnitude=0.05,
        shift_type=None,
        shifted_dimensions=[],
        interpretation="No significant behavioral shift detected. Insufficient data for analysis.",
    )
