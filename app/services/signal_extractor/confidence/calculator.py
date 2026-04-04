"""Signal confidence calculation for DISC behavioral signals.

Computes per-dimension and overall confidence scores from a set of
behavioral signals, applying exponential temporal decay so that recent
signals are weighted more heavily than older ones.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

# ---- constants ---------------------------------------------------------------

DISC_DIMENSIONS = ("D", "I", "S", "C")

# Minimum absolute decayed weight for a signal to count as "contributing"
CONTRIBUTION_THRESHOLD = 0.05

# Default exponential decay rate.
# λ = 0.015 ⇒ ~70 % weight retained at 30 days, ~22 % at 100 days.
DEFAULT_DECAY_RATE = 0.015

# Maximum per-dimension raw score before normalisation.  Used to map the
# aggregated (and decayed) weight sums into the 0-1 confidence range.
# This acts as a soft cap: accumulated weights above this value are clamped.
MAX_DIMENSION_SCORE = 3.0

# Minimum number of contributing signals for the overall confidence to be
# considered meaningful.  Below this threshold the score is penalised.
MIN_SIGNALS_FOR_FULL_CONFIDENCE = 3


# ---- public API --------------------------------------------------------------


def apply_temporal_decay(
    weight: float,
    days_ago: float,
    decay_rate: float = DEFAULT_DECAY_RATE,
) -> float:
    """Apply exponential temporal decay to a signal weight.

    Formula::

        decayed_weight = weight * e^(-decay_rate * days_ago)

    With the default λ = 0.015 the retained weight is approximately:

    * 100 % at 0 days
    *  ~86 % at 10 days
    *  ~64 % at 30 days
    *  ~22 % at 100 days

    Args:
        weight: Original signal weight (may be negative for penalty signals).
        days_ago: Number of days between the signal timestamp and "now".
            Negative values are clamped to 0 (future signals get no decay).
        decay_rate: Exponential decay constant (λ).  Larger values mean
            faster decay.

    Returns:
        The temporally-decayed weight.
    """
    if days_ago < 0:
        days_ago = 0.0
    return weight * math.exp(-decay_rate * days_ago)


def calculate_signal_confidence(
    signals: list[dict[str, Any]],
    window_days: int = 30,
    *,
    decay_rate: float = DEFAULT_DECAY_RATE,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calculate confidence for a set of behavioural signals.

    Each signal dict is expected to carry at least:

    * ``dimension`` – one of ``D``, ``I``, ``S``, ``C``
    * ``weight``    – numeric strength (positive or negative)
    * ``timestamp`` – ISO-8601 string **or** timezone-aware ``datetime``

    Signals whose ``dimension`` is not a valid DISC dimension, or whose
    ``timestamp`` falls outside the *window_days* look-back period, are
    silently skipped.

    Args:
        signals: Sequence of signal dicts.
        window_days: Maximum age (in days) of signals to consider.
        decay_rate: Exponential decay constant passed to
            :func:`apply_temporal_decay`.
        now: Reference "current" time.  Defaults to ``datetime.now(UTC)``.
            Exposed for deterministic testing.

    Returns:
        A dict with:

        * **dimension_scores** – ``dict[str, float]``  per-dimension
          confidence in ``[0, 1]``.
        * **overall_confidence** – ``float`` combined score in ``[0, 1]``.
        * **signal_count** – ``int`` total signals evaluated (within window).
        * **contributing_signals** – ``int`` signals whose decayed absolute
          weight exceeded :data:`CONTRIBUTION_THRESHOLD`.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Accumulators per dimension: sum of decayed weights and count of
    # contributing signals.
    dim_weights: dict[str, float] = {d: 0.0 for d in DISC_DIMENSIONS}
    dim_counts: dict[str, int] = {d: 0 for d in DISC_DIMENSIONS}

    signal_count = 0
    contributing_signals = 0

    for sig in signals:
        dimension = sig.get("dimension")
        if dimension not in DISC_DIMENSIONS:
            continue

        weight = sig.get("weight")
        if weight is None:
            continue
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            continue

        # Parse timestamp
        ts = _parse_timestamp(sig.get("timestamp"))
        if ts is None:
            continue

        days_ago = (now - ts).total_seconds() / 86_400.0

        # Skip signals outside the analysis window
        if days_ago > window_days:
            continue

        signal_count += 1

        decayed = apply_temporal_decay(weight, days_ago, decay_rate)

        dim_weights[dimension] += decayed

        if abs(decayed) >= CONTRIBUTION_THRESHOLD:
            dim_counts[dimension] += 1
            contributing_signals += 1

    # ---- per-dimension confidence scores ------------------------------------
    dimension_scores: dict[str, float] = {}
    for dim in DISC_DIMENSIONS:
        raw = dim_weights[dim]
        # Normalise into [0, 1] using a soft cap.  Negative aggregated
        # weights map to 0 (no confidence in that dimension).
        normalised = max(0.0, min(raw / MAX_DIMENSION_SCORE, 1.0))
        dimension_scores[dim] = round(normalised, 4)

    # ---- overall confidence -------------------------------------------------
    # Average of per-dimension scores, penalised when we have very few
    # contributing signals.
    if signal_count == 0:
        overall = 0.0
    else:
        raw_overall = sum(dimension_scores.values()) / len(DISC_DIMENSIONS)
        # Penalty factor for low signal count
        coverage = min(contributing_signals / MIN_SIGNALS_FOR_FULL_CONFIDENCE, 1.0)
        overall = raw_overall * coverage

    return {
        "dimension_scores": dimension_scores,
        "overall_confidence": round(overall, 4),
        "signal_count": signal_count,
        "contributing_signals": contributing_signals,
    }


# ---- internal helpers --------------------------------------------------------


def _parse_timestamp(value: Any) -> datetime | None:
    """Best-effort parse of a timestamp into a timezone-aware datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None
    return None
