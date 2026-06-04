"""Career profile and preference index endpoints.

Provides read-only access to a user's career profile (parsed from CV data)
and computed preference indexes derived from behavioral signals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, resolve_user_id
from app.api.v1.schemas.career import (
    CareerAnalytics,
    CareerProfileResponse,
    JobEntry as JobEntrySchema,
    PreferenceIndexes,
    PreferenceIndexValue,
    PreferencesResponse,
    TurningPoint,
)
from app.models.career import (
    CareerAnalytics as CareerAnalyticsModel,
    CareerTurningPoint,
    JobEntry as JobEntryModel,
)

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(tags=["career"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _label_for_value(value: float, neg_label: str, pos_label: str, neutral: str = "Neutral") -> str:
    """Return a human-readable label for a bipolar index value."""
    if value < -0.3:
        return neg_label
    if value > 0.3:
        return pos_label
    return neutral


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/users/{user_id}/career",
    response_model=CareerProfileResponse,
    summary="Get career profile",
    description=(
        "Return the career profile for a user, including aggregate analytics, "
        "job entries, and detected turning points."
    ),
)
async def get_career_profile(
    user_id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CareerProfileResponse:
    """Return career profile for the given user from real database data."""
    uid = resolve_user_id(user_id, _current_user)

    # Query job entries
    result = await db.execute(
        select(JobEntryModel)
        .where(JobEntryModel.user_id == uid)
        .order_by(JobEntryModel.start_date.desc())
    )
    job_rows = result.scalars().all()

    # Query analytics
    result = await db.execute(
        select(CareerAnalyticsModel).where(CareerAnalyticsModel.user_id == uid)
    )
    analytics_row = result.scalar_one_or_none()

    # Query turning points
    result = await db.execute(
        select(CareerTurningPoint)
        .where(CareerTurningPoint.user_id == uid)
    )
    tp_rows = result.scalars().all()

    # Map DB job entries to schema
    job_entries = [
        JobEntrySchema(
            title=row.job_title or "Unknown",
            company=row.company_name or "Unknown",
            start_date=row.start_date.isoformat() if row.start_date else None,
            end_date=row.end_date.isoformat() if row.end_date else None,
            duration_months=row.duration_months,
        )
        for row in job_rows
    ]

    # Map DB turning points to schema
    turning_points = [
        TurningPoint(
            date=None,  # No direct date field on the model
            description=tp.context_text or tp.inferred_motive or f"{tp.point_type.value} detected",
            type=tp.point_type.value,
        )
        for tp in tp_rows
    ]

    # Build analytics from DB or defaults
    if analytics_row:
        distinct_companies = len({row.company_name for row in job_rows if row.company_name})
        analytics = CareerAnalytics(
            total_experience_months=int(float(analytics_row.career_span_years or 0) * 12),
            avg_tenure_months=float(analytics_row.avg_tenure_months or 0),
            distinct_companies=distinct_companies,
            distinct_roles=analytics_row.total_roles or 0,
        )
    else:
        analytics = CareerAnalytics()

    return CareerProfileResponse(
        user_id=uid,
        analytics=analytics,
        job_entries=job_entries,
        turning_points=turning_points,
    )


@router.get(
    "/users/{user_id}/preferences",
    response_model=PreferencesResponse,
    summary="Get preference indexes",
    description=(
        "Return computed preference indexes for a user, derived from "
        "behavioral signals and career history analysis."
    ),
)
async def get_preferences(
    user_id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreferencesResponse:
    """Return computed preference indexes derived from career analytics."""
    uid = resolve_user_id(user_id, _current_user)

    # Query analytics
    result = await db.execute(
        select(CareerAnalyticsModel).where(CareerAnalyticsModel.user_id == uid)
    )
    analytics = result.scalar_one_or_none()

    if analytics:
        volatility = float(analytics.career_volatility_score or 0)
        avg_tenure = float(analytics.avg_tenure_months or 0)
        cross_industry = analytics.cross_industry_transitions or 0
        transition_freq = float(analytics.transition_frequency or 0)

        # stability_vs_growth: -1 (stability) to 1 (growth)
        # High volatility + low tenure => growth-oriented (positive)
        # Low volatility + high tenure => stability-oriented (negative)
        sg_value = round(min(1.0, max(-1.0, volatility * 1.5 - (avg_tenure / 60))), 2)
        sg_label = _label_for_value(sg_value, "Stability-oriented", "Growth-oriented")
        sg_interp = (
            f"Based on career volatility ({volatility:.2f}) and avg tenure ({avg_tenure:.0f}mo)."
        )

        # conservative_vs_aggressive_risk: -1 (conservative) to 1 (aggressive)
        risk_value = round(min(1.0, max(-1.0, cross_industry * 0.2 + volatility - 0.5)), 2)
        risk_label = _label_for_value(risk_value, "Conservative", "Aggressive")
        risk_interp = (
            f"Derived from {cross_industry} cross-industry transitions and "
            f"volatility score ({volatility:.2f})."
        )

        # control_vs_collaboration: neutral (no behavioral data yet)
        ctrl_value = 0.0
        ctrl_label = "Balanced"
        ctrl_interp = "Insufficient behavioral data to determine leadership style."

        # short_term_vs_long_term: -1 (short-term) to 1 (long-term)
        # High tenure + low transition freq => long-term (positive)
        st_value = round(min(1.0, max(-1.0, (avg_tenure / 48) - transition_freq)), 2)
        st_label = _label_for_value(st_value, "Short-term focus", "Long-term focus")
        st_interp = (
            f"Derived from avg tenure ({avg_tenure:.0f}mo) and "
            f"transition frequency ({transition_freq:.2f}/yr)."
        )

        # consistency_score: 0 to 1
        consistency = round(max(0.0, min(1.0, 1.0 - volatility)), 2)
        cons_label = "High" if consistency > 0.7 else ("Moderate" if consistency > 0.4 else "Low")
        cons_interp = f"Career consistency score based on volatility ({volatility:.2f})."

        indexes = PreferenceIndexes(
            stability_vs_growth=PreferenceIndexValue(
                value=sg_value, label=sg_label, interpretation=sg_interp,
            ),
            conservative_vs_aggressive_risk=PreferenceIndexValue(
                value=risk_value, label=risk_label, interpretation=risk_interp,
            ),
            control_vs_collaboration=PreferenceIndexValue(
                value=ctrl_value, label=ctrl_label, interpretation=ctrl_interp,
            ),
            short_term_vs_long_term=PreferenceIndexValue(
                value=st_value, label=st_label, interpretation=st_interp,
            ),
            consistency_score=PreferenceIndexValue(
                value=consistency, label=cons_label, interpretation=cons_interp,
            ),
        )
    else:
        # No analytics data — return neutral defaults
        indexes = PreferenceIndexes(
            stability_vs_growth=PreferenceIndexValue(
                value=0.0, label="Neutral",
                interpretation="Insufficient data to determine orientation.",
            ),
            conservative_vs_aggressive_risk=PreferenceIndexValue(
                value=0.0, label="Moderate",
                interpretation="Insufficient data to determine risk appetite.",
            ),
            control_vs_collaboration=PreferenceIndexValue(
                value=0.0, label="Balanced",
                interpretation="Insufficient data to determine leadership style.",
            ),
            short_term_vs_long_term=PreferenceIndexValue(
                value=0.0, label="Neutral",
                interpretation="Insufficient data to determine planning horizon.",
            ),
            consistency_score=PreferenceIndexValue(
                value=0.5, label="Moderate",
                interpretation="Insufficient data to determine consistency.",
            ),
        )

    return PreferencesResponse(
        user_id=uid,
        computed_at=datetime.now(timezone.utc),
        indexes=indexes,
    )
