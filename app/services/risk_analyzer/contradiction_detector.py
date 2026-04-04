"""Contradiction Detector – CV vs platform DISC profile comparison.

Compares a CV-derived DISC profile against a platform-observed profile,
computes a normalized contradiction score, classifies the type of
contradiction, and assigns a severity tier.
"""

from __future__ import annotations

import logging
import math

from app.services.disc_scorer.scorer import DISCScores

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIMENSIONS: tuple[str, ...] = ("D", "I", "S", "C")

# Maximum possible Euclidean distance between two DISC vectors:
# sqrt((100-0)^2 * 4) = 200.0
_MAX_DISTANCE: float = 200.0

# Contradiction score above which threshold_exceeded is True
_CONTRADICTION_THRESHOLD: float = 0.30

# Per-dimension gap (absolute points) above which a dimension is flagged
_DIMENSION_FLAG_THRESHOLD: float = 25.0

# Classification thresholds for specific contradiction types
_HIGH_THRESHOLD: float = 70.0
_LOW_THRESHOLD: float = 40.0

# ---------------------------------------------------------------------------
# Severity tier boundaries (from spec)
# ---------------------------------------------------------------------------

_SEVERITY_TIERS: list[tuple[float, str]] = [
    (0.70, "severe_contradiction"),
    (0.50, "high_contradiction"),
    (0.30, "significant_contradiction"),
    (0.15, "minor_divergence"),
    (0.00, "consistent"),
]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def compute_disc_distance(a: DISCScores, b: DISCScores) -> float:
    """Euclidean distance between two DISC vectors, normalized to 0-1.

    Max possible distance (0,0,0,0) vs (100,100,100,100) = ~200.

    Args:
        a: First DISC profile.
        b: Second DISC profile.

    Returns:
        Normalized distance in ``[0.0, 1.0]``.
    """
    sum_sq = (
        (a.d - b.d) ** 2
        + (a.i - b.i) ** 2
        + (a.s - b.s) ** 2
        + (a.c - b.c) ** 2
    )
    return math.sqrt(sum_sq) / _MAX_DISTANCE


def _get_score(profile: DISCScores, dim: str) -> float:
    """Extract score for a DISC dimension from a profile."""
    return getattr(profile, dim.lower())


def _determine_severity_tier(score: float) -> str:
    """Map a contradiction score to a severity tier.

    | Score     | Tier                      |
    |-----------|---------------------------|
    | 0.00-0.15 | consistent                |
    | 0.15-0.30 | minor_divergence          |
    | 0.30-0.50 | significant_contradiction |
    | 0.50-0.70 | high_contradiction        |
    | > 0.70    | severe_contradiction      |
    """
    for threshold, tier in _SEVERITY_TIERS:
        if score > threshold:
            return tier
    return "consistent"


def classify_contradiction(
    cv: DISCScores,
    platform: DISCScores,
    flagged: dict[str, float],
) -> str:
    """Classify the nature of the contradiction.

    Checks specific patterns in priority order:

    1. ``"stated_dominance_not_observed"`` — High D on CV (>= 70),
       low D on platform (<= 40).
    2. ``"stability_recovery_pattern"`` — Low S on CV (<= 40),
       high S on platform (>= 70).
    3. ``"conscientiousness_performance_gap"`` — High C on CV (>= 70),
       low C on platform (<= 40).
    4. ``"emerging_interpersonal_style"`` — High I on platform (>= 70),
       low I on CV (<= 40).
    5. ``"multi_dimension_divergence"`` — fallback for complex cases.
    6. ``"none"`` — no flagged dimensions.

    Args:
        cv: CV-derived DISC profile.
        platform: Platform-observed DISC profile.
        flagged: Dict of flagged dimensions with their gap values.

    Returns:
        One of the six contradiction type strings.
    """
    if not flagged:
        return "none"

    # 1. Stated dominance not observed: High D on CV, low D on platform
    if (
        "D" in flagged
        and cv.d >= _HIGH_THRESHOLD
        and platform.d <= _LOW_THRESHOLD
    ):
        return "stated_dominance_not_observed"

    # 2. Stability recovery pattern: Low S on CV, high S on platform
    if (
        "S" in flagged
        and cv.s <= _LOW_THRESHOLD
        and platform.s >= _HIGH_THRESHOLD
    ):
        return "stability_recovery_pattern"

    # 3. Conscientiousness performance gap: High C on CV, low C on platform
    if (
        "C" in flagged
        and cv.c >= _HIGH_THRESHOLD
        and platform.c <= _LOW_THRESHOLD
    ):
        return "conscientiousness_performance_gap"

    # 4. Emerging interpersonal style: High I on platform, low I on CV
    if (
        "I" in flagged
        and platform.i >= _HIGH_THRESHOLD
        and cv.i <= _LOW_THRESHOLD
    ):
        return "emerging_interpersonal_style"

    # 5. Fallback for complex cases
    return "multi_dimension_divergence"


def compute_contradiction_score(
    cv_profile: DISCScores,
    platform_profile: DISCScores,
) -> dict:
    """Compare CV-derived vs platform-observed DISC profiles.

    Computes the overall contradiction score (Euclidean distance),
    identifies per-dimension gaps, flags dimensions with large gaps,
    classifies the contradiction type, and assigns a severity tier.

    Args:
        cv_profile: DISC scores derived from CV analysis.
        platform_profile: DISC scores observed from platform behavior.

    Returns:
        Dict with keys:
            - ``contradiction_score``: float (0-1)
            - ``threshold_exceeded``: bool (score > 0.30)
            - ``dimension_gaps``: dict[str, float] (per-dimension absolute gap)
            - ``flagged_dimensions``: dict[str, float] (gaps > 25 points)
            - ``contradiction_type``: str (classification)
            - ``severity_tier``: str (consistent/minor/significant/high/severe)
    """
    # Overall contradiction score
    score = compute_disc_distance(cv_profile, platform_profile)

    # Per-dimension absolute gaps
    dimension_gaps: dict[str, float] = {}
    for dim in DIMENSIONS:
        cv_val = _get_score(cv_profile, dim)
        plat_val = _get_score(platform_profile, dim)
        dimension_gaps[dim] = abs(cv_val - plat_val)

    # Flag dimensions with gaps exceeding threshold
    flagged_dimensions: dict[str, float] = {
        dim: gap
        for dim, gap in dimension_gaps.items()
        if gap > _DIMENSION_FLAG_THRESHOLD
    }

    # Classify contradiction type
    contradiction_type = classify_contradiction(
        cv_profile, platform_profile, flagged_dimensions
    )

    # Severity tier
    severity_tier = _determine_severity_tier(score)

    logger.info(
        "Contradiction detection: score=%.4f type=%s severity=%s "
        "flagged_dims=%s",
        score,
        contradiction_type,
        severity_tier,
        list(flagged_dimensions.keys()),
    )

    return {
        "contradiction_score": round(score, 4),
        "threshold_exceeded": score > _CONTRADICTION_THRESHOLD,
        "dimension_gaps": dimension_gaps,
        "flagged_dimensions": flagged_dimensions,
        "contradiction_type": contradiction_type,
        "severity_tier": severity_tier,
    }
