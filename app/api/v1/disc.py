"""DISC profile query endpoints.

Provides endpoints to retrieve a user's DISC personality profile and
browse historical profile snapshots.  Computes DISC scores from career
analytics signals stored in the database.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_disc_cache, resolve_user_id
from app.api.v1.schemas.disc import (
    DISCHistoryEntry,
    DISCProfileHistoryResponse,
    DISCProfileResponse,
    DISCScores,
    WindowParam,
)
from app.models.career import CareerAnalytics as CareerAnalyticsModel
from app.models.user import User

if TYPE_CHECKING:
    from app.cache.disc_cache import DISCProfileCache

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["disc"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WINDOW_TO_DAYS: dict[str, int | None] = {
    "30d": 30,
    "90d": 90,
    "lifetime": None,
}


def _compute_disc_from_analytics(analytics: CareerAnalyticsModel) -> DISCScores:
    """Compute DISC scores from career analytics using signal weight formulas.

    D (Dominance): driven by upward_moves, transition_frequency, career_volatility
    I (Influence): driven by cross_industry_transitions, functional/industry diversity
    S (Steadiness): driven by avg_tenure, low volatility
    C (Conscientiousness): driven by industry focus, consistent patterns
    """
    d_raw = min(100, max(0,
        (analytics.upward_moves or 0) * 12
        + float(analytics.career_volatility_score or 0) * 40
        + float(analytics.transition_frequency or 0) * 25
        + 15  # base
    ))
    i_raw = min(100, max(0,
        (analytics.cross_industry_transitions or 0) * 10
        + float(analytics.functional_diversity_score or 0) * 30
        + float(analytics.industry_diversity_score or 0) * 30
        + 15
    ))
    s_raw = min(100, max(0,
        min(float(analytics.avg_tenure_months or 0) / 60 * 50, 50)
        + (1 - float(analytics.career_volatility_score or 0)) * 30
        + 15
    ))
    c_raw = min(100, max(0,
        (1 - float(analytics.industry_diversity_score or 0)) * 25
        + (1 - float(analytics.functional_diversity_score or 0)) * 25
        + min((analytics.longest_tenure_months or 0) / 48 * 25, 25)
        + 15
    ))
    return DISCScores(
        D=round(d_raw, 1),
        I=round(i_raw, 1),
        S=round(s_raw, 1),
        C=round(c_raw, 1),
    )


def _dominant_secondary(scores: DISCScores) -> tuple[str, str]:
    """Derive dominant and secondary traits from scores."""
    ranked = sorted(
        [("D", scores.D), ("I", scores.I), ("S", scores.S), ("C", scores.C)],
        key=lambda t: t[1],
        reverse=True,
    )
    return ranked[0][0], ranked[1][0]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/users/{user_id}/disc-profile",
    response_model=DISCProfileResponse,
    summary="Get a user's DISC profile",
    description=(
        "Retrieve the latest DISC personality profile for a user within the "
        "requested analysis window, computed from career analytics signals."
    ),
)
async def get_disc_profile(
    user_id: str,
    window: WindowParam = Query(
        WindowParam.DAYS_90,
        description="Analysis window: 30d, 90d, or lifetime.",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    disc_cache: DISCProfileCache | None = Depends(get_disc_cache),
) -> DISCProfileResponse:
    """Return the DISC profile for *user_id*.

    Checks the Redis cache first.  On a miss, computes the profile from
    career analytics and caches it for subsequent requests.  If Redis is
    unavailable the endpoint works normally without caching.
    """
    uid = resolve_user_id(user_id, current_user)
    uid_str = str(uid)

    # --- Try cache ---
    if disc_cache is not None:
        try:
            cached = await disc_cache.get_profile(uid_str, window.value)
            if cached is not None:
                return DISCProfileResponse(**cached)
        except Exception:
            logger.warning("disc_cache_read_error", user_id=uid_str, exc_info=True)

    # --- Compute from career analytics ---
    result = await db.execute(
        select(CareerAnalyticsModel).where(CareerAnalyticsModel.user_id == uid)
    )
    analytics = result.scalar_one_or_none()

    if analytics:
        scores = _compute_disc_from_analytics(analytics)
        confidence = min(1.0, (analytics.total_roles or 0) / 5)
        data_sources = analytics.total_roles or 0
    else:
        scores = DISCScores(D=0, I=0, S=0, C=0)
        confidence = 0.0
        data_sources = 0

    dominant, secondary = _dominant_secondary(scores)

    response = DISCProfileResponse(
        user_id=uid,
        window=window.value,
        computed_at=datetime.now(timezone.utc),
        confidence=round(confidence, 3),
        scores=scores,
        dominant=dominant,
        secondary=secondary,
        data_sources=data_sources,
    )

    # --- Populate cache ---
    if disc_cache is not None:
        try:
            await disc_cache.set_profile(
                uid_str, window.value, response.model_dump(mode="json"),
            )
        except Exception:
            logger.warning("disc_cache_write_error", user_id=uid_str, exc_info=True)

    return response


@router.get(
    "/users/{user_id}/disc-profile/history",
    response_model=DISCProfileHistoryResponse,
    summary="Get DISC profile history",
    description=(
        "Retrieve historical DISC profile snapshots for a user over a date "
        "range.  Returns placeholder data in Phase 6."
    ),
)
async def get_disc_profile_history(
    user_id: str,
    window: WindowParam = Query(
        WindowParam.DAYS_90,
        description="Analysis window for each snapshot: 30d, 90d, or lifetime.",
    ),
    from_date: datetime | None = Query(
        None,
        alias="from",
        description="Start of date range (ISO-8601). Defaults to 6 months ago.",
    ),
    to_date: datetime | None = Query(
        None,
        alias="to",
        description="End of date range (ISO-8601). Defaults to now.",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DISCProfileHistoryResponse:
    """Return historical DISC profile snapshots for *user_id*.

    Currently returns deterministic mock history.  A future phase will
    query ``disc_profiles`` filtered by ``computed_at`` range.
    """
    uid = resolve_user_id(user_id, current_user)

    now = datetime.now(timezone.utc)
    end = to_date or now
    start = from_date or (now - timedelta(days=180))

    # Generate a few mock snapshots spread across the range
    total_span = (end - start).total_seconds()
    snapshot_count = 5
    history: list[DISCHistoryEntry] = []

    for i in range(snapshot_count):
        offset = timedelta(seconds=total_span * i / max(snapshot_count - 1, 1))
        ts = start + offset
        # Vary scores slightly per snapshot for realism
        scores = DISCScores(
            D=round(60.0 + i * 1.2, 1),
            I=round(44.0 - i * 0.5, 1),
            S=round(70.0 + i * 0.8, 1),
            C=round(52.0 + i * 0.3, 1),
        )
        dominant, _ = _dominant_secondary(scores)
        history.append(
            DISCHistoryEntry(
                computed_at=ts,
                scores=scores,
                dominant=dominant,
            )
        )

    return DISCProfileHistoryResponse(
        user_id=uid,
        history=history,
    )
