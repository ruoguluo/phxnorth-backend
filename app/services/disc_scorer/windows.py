"""Multi-window DISC scoring — produces profiles at 3 temporal windows.

Computes DISC profiles for 30-day, 90-day, and lifetime windows by
filtering signals to each window's cutoff date and delegating to
:func:`~app.services.disc_scorer.scorer.compute_disc_scores`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.disc_scorer.scorer import (
    DISCScores,
    WeightedSignal,
    compute_disc_scores,
)

# ---------------------------------------------------------------------------
# Window definitions
# ---------------------------------------------------------------------------

WINDOWS: dict[str, int | None] = {
    "30d": 30,
    "90d": 90,
    "lifetime": None,
}
"""Mapping of window label → max age in days (``None`` = no limit)."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_windowed_profiles(
    signals: list[WeightedSignal],
    now: datetime | None = None,
) -> dict[str, DISCScores]:
    """Compute DISC profiles at 3 temporal windows.

    For each window the input signals are filtered to those whose
    ``timestamp`` falls within the window's cutoff, then scored via
    :func:`compute_disc_scores`.

    Args:
        signals: Pre-built weighted signals (any age).
        now: Reference "current" time.  Defaults to
            ``datetime.now(timezone.utc)`` when ``None``.

    Returns:
        Dict with keys ``"30d"``, ``"90d"``, ``"lifetime"`` each
        mapping to a :class:`DISCScores` instance.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    results: dict[str, DISCScores] = {}

    for label, max_days in WINDOWS.items():
        if max_days is None:
            # Lifetime — no filtering
            filtered = signals
        else:
            cutoff = now - timedelta(days=max_days)
            filtered = [
                s for s in signals
                if _ensure_tz(s.timestamp) >= cutoff
            ]

        results[label] = compute_disc_scores(filtered, now=now)

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_tz(dt: datetime) -> datetime:
    """Return *dt* with UTC tzinfo attached if it was naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
