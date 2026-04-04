"""DISC profile query endpoints.

Provides endpoints to retrieve a user's DISC personality profile and
browse historical profile snapshots.  In Phase 6 these return
placeholder/mock data; a later phase will wire them to the real
disc_profiles table via the DISC engine service.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_disc_cache
from app.api.v1.schemas.disc import (
    DISCHistoryEntry,
    DISCProfileHistoryResponse,
    DISCProfileResponse,
    DISCScores,
    WindowParam,
)
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


def _mock_scores() -> DISCScores:
    """Return deterministic placeholder DISC scores."""
    return DISCScores(D=62.5, I=45.0, S=71.3, C=53.8)


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
        "requested analysis window.  Returns placeholder data in Phase 6."
    ),
)
async def get_disc_profile(
    user_id: UUID,
    window: WindowParam = Query(
        WindowParam.DAYS_90,
        description="Analysis window: 30d, 90d, or lifetime.",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    disc_cache: DISCProfileCache | None = Depends(get_disc_cache),
) -> DISCProfileResponse:
    """Return the DISC profile for *user_id*.

    Checks the Redis cache first.  On a miss, computes the profile and
    caches it for subsequent requests.  If Redis is unavailable the
    endpoint works normally without caching.
    """
    uid = str(user_id)

    # --- Try cache ---
    if disc_cache is not None:
        try:
            cached = await disc_cache.get_profile(uid, window.value)
            if cached is not None:
                return DISCProfileResponse(**cached)
        except Exception:
            logger.warning("disc_cache_read_error", user_id=uid, exc_info=True)

    # --- Compute ---
    scores = _mock_scores()
    dominant, secondary = _dominant_secondary(scores)

    response = DISCProfileResponse(
        user_id=user_id,
        window=window.value,
        computed_at=datetime.now(timezone.utc),
        confidence=0.82,
        scores=scores,
        dominant=dominant,
        secondary=secondary,
        data_sources=47,
    )

    # --- Populate cache ---
    if disc_cache is not None:
        try:
            await disc_cache.set_profile(
                uid, window.value, response.model_dump(mode="json"),
            )
        except Exception:
            logger.warning("disc_cache_write_error", user_id=uid, exc_info=True)

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
    user_id: UUID,
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
        user_id=user_id,
        history=history,
    )
