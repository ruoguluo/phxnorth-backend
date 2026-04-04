"""Career profile and preference index endpoints.

Provides read-only access to a user's career profile (parsed from CV data)
and computed preference indexes derived from behavioral signals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.v1.schemas.career import (
    CareerAnalytics,
    CareerProfileResponse,
    PreferenceIndexes,
    PreferenceIndexValue,
    PreferencesResponse,
)

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(tags=["career"])


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
    user_id: UUID,
    _current_user: User = Depends(get_current_user),
) -> CareerProfileResponse:
    """Return career profile for the given user.

    This is a placeholder that returns a structured empty response.
    Real data will be populated once CV parsing results are persisted.
    """
    # TODO: Fetch real career data from the database (Phase 7+)
    return CareerProfileResponse(
        user_id=user_id,
        analytics=CareerAnalytics(),
        job_entries=[],
        turning_points=[],
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
    user_id: UUID,
    _current_user: User = Depends(get_current_user),
) -> PreferencesResponse:
    """Return computed preference indexes for the given user.

    This is a placeholder that returns neutral/default index values.
    Real computation will be wired in once the scoring pipeline is active.
    """
    # TODO: Compute real indexes from stored signals (Phase 7+)
    return PreferencesResponse(
        user_id=user_id,
        computed_at=datetime.now(timezone.utc),
        indexes=PreferenceIndexes(
            stability_vs_growth=PreferenceIndexValue(
                value=0.0,
                label="Neutral",
                interpretation="Insufficient data to determine orientation.",
            ),
            conservative_vs_aggressive_risk=PreferenceIndexValue(
                value=0.0,
                label="Moderate",
                interpretation="Insufficient data to determine risk appetite.",
            ),
            control_vs_collaboration=PreferenceIndexValue(
                value=0.0,
                label="Balanced",
                interpretation="Insufficient data to determine leadership style.",
            ),
            short_term_vs_long_term=PreferenceIndexValue(
                value=0.0,
                label="Neutral",
                interpretation="Insufficient data to determine planning horizon.",
            ),
            consistency_score=PreferenceIndexValue(
                value=0.5,
                label="Moderate",
                interpretation="Insufficient data to determine consistency.",
            ),
        ),
    )
