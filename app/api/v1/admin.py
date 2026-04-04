"""Admin-only endpoints for signals, DISC recomputation, and red flags.

Provides privileged endpoints for administrators to inspect behavioral
signals, trigger DISC profile recomputation, and manage red flags.
All endpoints require ``require_admin`` authentication.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin
from app.api.v1.schemas.admin import (
    DISCRecomputeResponse,
    RedFlagItem,
    RedFlagListResponse,
    RedFlagSeverity,
    SignalItem,
    SignalSource,
    UserSignalsResponse,
)

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(tags=["admin"])


# ---------------------------------------------------------------------------
# GET /admin/users/{user_id}/signals
# ---------------------------------------------------------------------------


@router.get(
    "/users/{user_id}/signals",
    response_model=UserSignalsResponse,
    summary="View user signals",
    description=(
        "Retrieve behavioral signals for a user, optionally filtered by "
        "source and date range.  Returns placeholder data in Phase 6."
    ),
)
async def get_user_signals(
    user_id: UUID,
    source: SignalSource = Query(
        SignalSource.ALL,
        description="Filter signals by source: cv, platform, or all.",
    ),
    from_date: datetime | None = Query(
        None,
        alias="from",
        description="Start of date range (ISO-8601). Defaults to 30 days ago.",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of signals to return.",
    ),
    _admin_user: User = Depends(require_admin),
) -> UserSignalsResponse:
    """Return behavioral signals for the given user.

    Currently returns mock data.  A future phase will query the
    signals table filtered by source, date range, and limit.
    """
    now = datetime.now(timezone.utc)
    start = from_date or (now - timedelta(days=30))

    # Build mock signals respecting the source filter
    mock_signals: list[SignalItem] = []
    signal_templates = [
        ("response_time", "platform", 0.85, "Average response time decreased by 15%."),
        ("keyword_frequency", "cv", 0.72, "Leadership keywords appear 3x in latest CV."),
        ("engagement_score", "platform", 0.91, "Daily active engagement above threshold."),
        ("skill_claim", "cv", 0.68, "New skill claim: project management."),
        ("login_pattern", "platform", 0.77, "Login frequency increased over last 7 days."),
    ]

    for i, (sig_type, sig_source, confidence, evidence) in enumerate(signal_templates):
        if source != SignalSource.ALL and sig_source != source.value:
            continue
        ts = start + timedelta(hours=i * 6)
        mock_signals.append(
            SignalItem(
                signal_id=f"sig-{uuid4().hex[:12]}",
                signal_type=sig_type,
                source=sig_source,
                confidence=confidence,
                timestamp=ts,
                evidence=evidence,
            )
        )
        if len(mock_signals) >= limit:
            break

    return UserSignalsResponse(user_id=user_id, signals=mock_signals)


# ---------------------------------------------------------------------------
# POST /admin/users/{user_id}/disc/recompute
# ---------------------------------------------------------------------------


@router.post(
    "/users/{user_id}/disc/recompute",
    response_model=DISCRecomputeResponse,
    status_code=202,
    summary="Trigger DISC recompute",
    description=(
        "Queue a DISC profile recomputation for a user.  Returns a job ID "
        "that can be used to track the computation status.  Returns a "
        "placeholder response in Phase 6."
    ),
)
async def trigger_disc_recompute(
    user_id: UUID,
    _admin_user: User = Depends(require_admin),
) -> DISCRecomputeResponse:
    """Queue a DISC recomputation job for the given user.

    Currently returns a mock job reference.  A future phase will
    enqueue the job via the task queue and return a real job ID.
    """
    job_id = f"job-{uuid4().hex[:12]}"

    return DISCRecomputeResponse(
        job_id=job_id,
        status="queued",
        message=f"DISC recomputation queued for user {user_id}.",
    )


# ---------------------------------------------------------------------------
# GET /admin/red-flags
# ---------------------------------------------------------------------------


@router.get(
    "/red-flags",
    response_model=RedFlagListResponse,
    summary="List red flags",
    description=(
        "Retrieve red flags across all users, optionally filtered by severity "
        "and resolution status.  Returns placeholder data in Phase 6."
    ),
)
async def list_red_flags(
    severity: RedFlagSeverity | None = Query(
        None,
        description="Filter by severity: red or orange.",
    ),
    resolved: bool | None = Query(
        None,
        description="Filter by resolution status.",
    ),
    from_date: datetime | None = Query(
        None,
        alias="from",
        description="Only return flags created after this date (ISO-8601).",
    ),
    _admin_user: User = Depends(require_admin),
) -> RedFlagListResponse:
    """Return red flags matching the given filters.

    Currently returns mock data.  A future phase will query the
    red_flags table with the supplied filters.
    """
    now = datetime.now(timezone.utc)

    mock_flags = [
        RedFlagItem(
            id="rf-001",
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            flag_type="contradiction",
            severity="red",
            description="High contradiction between self-reported and observed behavior.",
            created_at=now - timedelta(days=2),
            resolved=False,
        ),
        RedFlagItem(
            id="rf-002",
            user_id=UUID("00000000-0000-0000-0000-000000000002"),
            flag_type="anomaly",
            severity="orange",
            description="Unusual engagement pattern detected in last 7 days.",
            created_at=now - timedelta(days=1),
            resolved=False,
        ),
        RedFlagItem(
            id="rf-003",
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            flag_type="behavioral_shift",
            severity="red",
            description="Sudden behavioral shift in Dominance dimension.",
            created_at=now - timedelta(hours=12),
            resolved=True,
        ),
    ]

    # Apply filters
    filtered = mock_flags

    if severity is not None:
        filtered = [f for f in filtered if f.severity == severity.value]

    if resolved is not None:
        filtered = [f for f in filtered if f.resolved == resolved]

    if from_date is not None:
        filtered = [f for f in filtered if f.created_at >= from_date]

    return RedFlagListResponse(total=len(filtered), flags=filtered)
