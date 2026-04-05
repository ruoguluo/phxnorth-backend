"""Risk assessment, contradiction analysis, and behavioral shift endpoints.

Computes risk scores from career analytics stored in the database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_risk_cache
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
from app.models.career import CareerAnalytics as CareerAnalyticsModel

if TYPE_CHECKING:
    from app.cache.risk_cache import RiskCache
    from app.models.user import User

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["risk"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _severity(score: float) -> str:
    """Map a 0-1 risk score to a severity tier."""
    if score < 0.3:
        return "low"
    if score < 0.5:
        return "medium"
    if score < 0.7:
        return "high"
    return "critical"


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
    db: AsyncSession = Depends(get_db),
    risk_cache: RiskCache | None = Depends(get_risk_cache),
) -> RiskAssessmentResponse:
    """Return risk assessment for the given user.

    Checks the Redis cache first.  On a miss, computes the assessment
    from career analytics and caches it.  If Redis is unavailable the
    endpoint works normally without caching.
    """
    uid = str(user_id)

    # --- Try cache ---
    if risk_cache is not None:
        try:
            cached = await risk_cache.get_risk(uid)
            if cached is not None:
                return RiskAssessmentResponse(**cached)
        except Exception:
            logger.warning("risk_cache_read_error", user_id=uid, exc_info=True)

    # --- Compute from career analytics ---
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(CareerAnalyticsModel).where(CareerAnalyticsModel.user_id == user_id)
    )
    analytics = result.scalar_one_or_none()

    if analytics:
        volatility = float(analytics.career_volatility_score or 0)
        short_tenure_rate = float(analytics.short_tenure_rate or 0)
        transition_freq = float(analytics.transition_frequency or 0)

        # career_instability
        instability_score = round(volatility * 0.6 + short_tenure_rate * 0.4, 3)
        instability_sev = _severity(instability_score)

        # attrition risk
        attrition_score = round(short_tenure_rate * 0.5 + transition_freq * 0.3, 3)
        attrition_score = min(1.0, attrition_score)
        attrition_sev = _severity(attrition_score)

        # disengagement (default — no behavioral data yet)
        disengagement_score = 0.1
        disengagement_sev = "low"

        assessments = [
            RiskAssessmentItem(
                category="career_instability",
                score=instability_score,
                severity=instability_sev,
                description=(
                    f"Based on career volatility ({volatility:.2f}) and "
                    f"short-tenure rate ({short_tenure_rate:.2f})."
                ),
            ),
            RiskAssessmentItem(
                category="attrition",
                score=attrition_score,
                severity=attrition_sev,
                description=(
                    f"Derived from short-tenure rate ({short_tenure_rate:.2f}) and "
                    f"transition frequency ({transition_freq:.2f}/yr)."
                ),
            ),
            RiskAssessmentItem(
                category="disengagement",
                score=disengagement_score,
                severity=disengagement_sev,
                description="No behavioral data available yet; default low risk.",
            ),
        ]

        # Overall tier = highest severity across categories
        all_severities = [instability_sev, attrition_sev, disengagement_sev]
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        overall_risk_tier = max(all_severities, key=lambda s: severity_order.get(s, 0))

        # Active flags only if any category is high or critical
        active_flags: list[RiskFlag] = []
        for item in assessments:
            if item.severity in ("high", "critical"):
                active_flags.append(
                    RiskFlag(
                        flag_id=f"flag-{item.category}-{uid[:8]}",
                        category=item.category,
                        raised_at=now,
                        message=f"{item.category.replace('_', ' ').title()} risk is {item.severity}: {item.description}",
                    )
                )
    else:
        # No career data — return minimal defaults
        assessments = [
            RiskAssessmentItem(
                category="attrition",
                score=0.0,
                severity="low",
                description="No career data available for risk assessment.",
            ),
            RiskAssessmentItem(
                category="disengagement",
                score=0.0,
                severity="low",
                description="No career data available for risk assessment.",
            ),
        ]
        overall_risk_tier = "low"
        active_flags = []

    response = RiskAssessmentResponse(
        user_id=user_id,
        computed_at=now,
        overall_risk_tier=overall_risk_tier,
        assessments=assessments,
        active_flags=active_flags,
    )

    # --- Populate cache ---
    if risk_cache is not None:
        try:
            await risk_cache.set_risk(uid, response.model_dump(mode="json"))
        except Exception:
            logger.warning("risk_cache_write_error", user_id=uid, exc_info=True)

    return response


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
    db: AsyncSession = Depends(get_db),
) -> ContradictionResponse:
    """Return contradiction analysis computed from DISC-like career signals."""
    # Import here to avoid circular — we compute DISC inline from analytics
    from app.api.v1.disc import _compute_disc_from_analytics

    result = await db.execute(
        select(CareerAnalyticsModel).where(CareerAnalyticsModel.user_id == user_id)
    )
    analytics = result.scalar_one_or_none()

    if not analytics:
        return ContradictionResponse(
            user_id=user_id,
            contradiction_score=0.0,
            severity_tier="none",
            threshold_exceeded=False,
            dimension_gaps=[],
            flagged_dimensions=[],
            contradiction_type=None,
        )

    scores = _compute_disc_from_analytics(analytics)

    # Compute pairwise dimension gaps (normalised to 0-1 from 0-100 scale)
    dims = {"D": scores.D, "I": scores.I, "S": scores.S, "C": scores.C}
    pairs = [("D", "I"), ("D", "S"), ("D", "C"), ("I", "S"), ("I", "C"), ("S", "C")]
    dimension_gaps: list[DimensionGap] = []
    flagged: list[str] = []

    for a, b in pairs:
        gap = abs(dims[a] - dims[b]) / 100.0
        if gap > 0.15:  # Only report meaningful gaps
            higher = a if dims[a] > dims[b] else b
            lower = b if higher == a else a
            dimension_gaps.append(DimensionGap(
                dimension_a=a,
                dimension_b=b,
                gap=round(gap, 3),
                interpretation=f"{higher} significantly exceeds {lower} ({dims[higher]:.0f} vs {dims[lower]:.0f}).",
            ))
            if gap > 0.35:
                if a not in flagged:
                    flagged.append(a)
                if b not in flagged:
                    flagged.append(b)

    # Overall contradiction score = mean of top 2 gaps
    sorted_gaps = sorted([g.gap for g in dimension_gaps], reverse=True)
    if len(sorted_gaps) >= 2:
        contradiction_score = round((sorted_gaps[0] + sorted_gaps[1]) / 2, 3)
    elif sorted_gaps:
        contradiction_score = round(sorted_gaps[0] / 2, 3)
    else:
        contradiction_score = 0.0

    contradiction_score = min(1.0, contradiction_score)

    if contradiction_score < 0.15:
        severity_tier = "none"
    elif contradiction_score < 0.3:
        severity_tier = "low"
    elif contradiction_score < 0.5:
        severity_tier = "medium"
    else:
        severity_tier = "high"

    return ContradictionResponse(
        user_id=user_id,
        contradiction_score=contradiction_score,
        severity_tier=severity_tier,
        threshold_exceeded=contradiction_score > 0.4,
        dimension_gaps=dimension_gaps,
        flagged_dimensions=flagged,
        contradiction_type="career-signal divergence" if flagged else None,
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
