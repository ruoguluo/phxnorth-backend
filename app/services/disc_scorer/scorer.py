"""DISC Scorer – temporal-decay weighted scoring with soft normalization.

Takes weighted behavioral signals, applies exponential temporal decay,
accumulates per-dimension scores, and normalizes to 0-100 range.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from app.services.disc_scorer.weights.signal_weights import (
    SIGNAL_WEIGHTS,
    DISCWeights,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LAMBDA_DECAY: float = 0.015
"""Exponential decay rate (per day).

Reference points:
  Day  0 → w = 1.00
  Day 30 → w ≈ 0.64
  Day 90 → w ≈ 0.26
  Day 180 → w ≈ 0.07
"""

CONFIDENCE_THRESHOLD: float = 20.0
"""Total accumulated weight required for full confidence (1.0)."""

SECONDARY_MIN_SCORE: float = 35.0
"""Minimum normalized score for a dimension to qualify as secondary."""

MODEL_VERSION: str = "1.0"

DIMENSIONS: tuple[str, ...] = ("D", "I", "S", "C")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeightedSignal:
    """A single behavioral signal ready for DISC scoring.

    Attributes:
        signal_type: Identifier matching a key in ``SIGNAL_WEIGHTS``.
        confidence: Signal-level confidence in ``[0.0, 1.0]``.
        timestamp: When the signal was observed.
        source: Origin of the signal (``"cv"`` or ``"platform"``).
    """

    signal_type: str
    confidence: float
    timestamp: datetime
    source: str  # "cv" | "platform"


@dataclass
class DISCScores:
    """Computed DISC profile scores.

    Attributes:
        d: Dominance score (0-100).
        i: Influence score (0-100).
        s: Steadiness score (0-100).
        c: Conscientiousness score (0-100).
        confidence: Overall confidence in ``[0.0, 1.0]``.
        dominant: Highest-scoring dimension label.
        secondary: Second-highest dimension (or ``None`` if below threshold).
        signal_count: Number of recognized signals that contributed.
        computed_at: Timestamp of computation.
        model_version: Version string for the scoring model.
    """

    d: float
    i: float
    s: float
    c: float
    confidence: float
    dominant: str
    secondary: str | None
    signal_count: int
    computed_at: datetime
    model_version: str = MODEL_VERSION


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------


def compute_time_weight(
    signal_timestamp: datetime,
    now: datetime,
    lambda_decay: float = DEFAULT_LAMBDA_DECAY,
) -> float:
    """Compute exponential temporal decay weight for a signal.

    .. math::

        w(t) = e^{-\\lambda \\times \\text{days\\_ago}}

    Args:
        signal_timestamp: When the signal was observed.
        now: Reference "current" time.
        lambda_decay: Decay rate per day.

    Returns:
        Weight in ``(0.0, 1.0]``.  Returns ``1.0`` for signals
        at *now* or in the future.
    """
    delta = now - signal_timestamp
    days_ago = max(delta.total_seconds() / 86400.0, 0.0)
    return math.exp(-lambda_decay * days_ago)


def normalize_to_range(
    values: np.ndarray,
    low: float = 0.0,
    high: float = 100.0,
) -> np.ndarray:
    """Soft-normalize raw accumulator values to ``[low, high]``.

    Uses a sigmoid-inspired transform so that:
    * A raw score of 0 maps to the midpoint.
    * Positive raw scores push toward *high*.
    * Negative raw scores push toward *low*.

    The transform is: ``mid + (high - mid) × tanh(raw / scale)``
    where ``scale`` controls sensitivity.  With scale = 3.0 a raw
    score of ±3 roughly saturates the range.

    When all values are exactly zero, returns an array of midpoints.

    Args:
        values: 1-D array of raw accumulated DISC scores.
        low: Lower bound of output range.
        high: Upper bound of output range.

    Returns:
        Array of same shape with values in ``[low, high]``.
    """
    mid = (low + high) / 2.0
    span = (high - low) / 2.0
    scale = 3.0  # controls sigmoid sensitivity
    return mid + span * np.tanh(values / scale)


def compute_disc_scores(
    signals: list[WeightedSignal],
    now: datetime | None = None,
) -> DISCScores:
    """Compute a full DISC profile from weighted signals.

    Algorithm:
    1. For each signal whose ``signal_type`` is in the weight library,
       compute ``effective = time_weight × signal_confidence``.
    2. For each DISC dimension, accumulate
       ``raw[dim] += signal_disc_weight[dim] × effective``.
    3. Track ``total_weight += effective`` for confidence calculation.
    4. Normalize raw accumulators to 0-100 via :func:`normalize_to_range`.
    5. Confidence = ``min(total_weight / CONFIDENCE_THRESHOLD, 1.0)``.
    6. Dominant = highest dimension; secondary = second highest if > 35.

    Args:
        signals: Pre-built weighted signals.
        now: Reference time (defaults to ``datetime.now(timezone.utc)``).

    Returns:
        A :class:`DISCScores` instance.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Ensure *now* is timezone-aware for safe arithmetic
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Raw accumulators
    raw: dict[str, float] = {dim: 0.0 for dim in DIMENSIONS}
    total_weight: float = 0.0
    recognized_count: int = 0

    for signal in signals:
        weights: DISCWeights | None = SIGNAL_WEIGHTS.get(signal.signal_type)
        if weights is None:
            logger.warning(
                "Unknown signal type %r – skipping", signal.signal_type
            )
            continue

        # Make signal timestamp tz-aware if needed
        ts = signal.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        time_weight = compute_time_weight(ts, now)
        effective = time_weight * signal.confidence

        for dim in DIMENSIONS:
            raw[dim] += weights[dim] * effective  # type: ignore[literal-required]

        total_weight += effective
        recognized_count += 1

    # Normalize to 0-100
    raw_array = np.array([raw[dim] for dim in DIMENSIONS], dtype=np.float64)
    normalized = normalize_to_range(raw_array)

    scores = {dim: float(normalized[i]) for i, dim in enumerate(DIMENSIONS)}

    # Confidence
    confidence = min(total_weight / CONFIDENCE_THRESHOLD, 1.0)

    # Dominant / secondary detection
    sorted_dims = sorted(DIMENSIONS, key=lambda d: scores[d], reverse=True)
    dominant = sorted_dims[0]
    second = sorted_dims[1]
    secondary = second if scores[second] > SECONDARY_MIN_SCORE else None

    return DISCScores(
        d=round(scores["D"], 1),
        i=round(scores["I"], 1),
        s=round(scores["S"], 1),
        c=round(scores["C"], 1),
        confidence=round(confidence, 4),
        dominant=dominant,
        secondary=secondary,
        signal_count=recognized_count,
        computed_at=now,
        model_version=MODEL_VERSION,
    )
