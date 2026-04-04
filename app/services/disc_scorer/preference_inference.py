"""Preference inference – derive bipolar career/decision preference indexes.

Computes five bipolar preference indexes from DISC scores, career analytics,
and behavioral metrics.  Each index ranges from -1.0 to +1.0 except
``consistency_score`` which ranges from 0.0 to 1.0.

Formulas follow the PhxNorth Behavioral Intelligence Specification v1.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.services.disc_scorer.scorer import DISCScores

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreferenceIndexes:
    """Bipolar preference indexes derived from DISC scores and supporting data.

    Attributes:
        stability_vs_growth: -1.0 (stability-seeking) to +1.0 (growth-seeking).
        conservative_vs_aggressive_risk: -1.0 (conservative) to +1.0 (aggressive).
        control_vs_collaboration: -1.0 (collaboration) to +1.0 (control).
        short_term_vs_long_term: -1.0 (long-term) to +1.0 (short-term).
        consistency_score: 0.0 (inconsistent) to 1.0 (highly consistent).
    """

    stability_vs_growth: float
    conservative_vs_aggressive_risk: float
    control_vs_collaboration: float
    short_term_vs_long_term: float
    consistency_score: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp *value* to the inclusive range ``[low, high]``."""
    return max(low, min(high, value))


def _safe_get(mapping: dict, key: str, default: float = 0.0) -> float:
    """Extract a float from *mapping*, falling back to *default*.

    Handles ``None`` values gracefully so callers don't have to guard
    against missing or null entries in career_analytics / behavioral_metrics.
    """
    value = mapping.get(key, default)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.warning(
            "Non-numeric value %r for key %r – using default %s",
            value,
            key,
            default,
        )
        return default


# ---------------------------------------------------------------------------
# Core inference
# ---------------------------------------------------------------------------


def infer_preferences(
    disc: DISCScores,
    career_analytics: dict,
    behavioral_metrics: dict,
) -> PreferenceIndexes:
    """Infer bipolar preference indexes from DISC scores and supporting data.

    Args:
        disc: Computed DISC profile scores (each dimension 0-100).
        career_analytics: Career-derived metrics.  Expected keys:

            * ``career_volatility_score`` (float, 0-1)
            * ``avg_tenure_months`` (float, months)
            * ``cross_industry_transitions`` (int)
            * ``has_founder_experience`` (bool)
            * ``transition_frequency`` (float, 0-1)

        behavioral_metrics: Platform behavioral metrics.  Expected keys:

            * ``brief_direct_message_rate`` (float, 0-1)
            * ``warm_rapport_rate`` (float, 0-1)
            * ``mentorship_dropout_rate`` (float, 0-1)
            * ``contradiction_score`` (float, 0-1)
            * ``response_latency_cv`` (float, coefficient of variation)
            * ``engagement_variability`` (float, 0-1)

    Returns:
        A :class:`PreferenceIndexes` instance with all five indexes.
    """

    # Shorthand: DISC dimensions normalised to 0-1
    d = disc.d / 100.0
    i = disc.i / 100.0
    s = disc.s / 100.0
    c = disc.c / 100.0

    # -- 1. stability_vs_growth ------------------------------------------------
    career_volatility = _safe_get(career_analytics, "career_volatility_score")
    avg_tenure_months = _safe_get(career_analytics, "avg_tenure_months")

    raw_sg = (
        d * 0.35
        + i * 0.20
        - s * 0.30
        - c * 0.15
        + career_volatility * 0.40
        - (avg_tenure_months / 120.0) * 0.30
    )
    stability_vs_growth = _clamp(raw_sg * 2 - 1, -1.0, 1.0)

    # -- 2. conservative_vs_aggressive_risk ------------------------------------
    cross_industry = _safe_get(career_analytics, "cross_industry_transitions")
    has_founder = bool(career_analytics.get("has_founder_experience", False))

    raw_risk = (
        d * 0.40
        - s * 0.35
        - c * 0.20
        + (cross_industry / 5.0) * 0.20
        + (1.0 if has_founder else 0.0) * 0.25
    )
    conservative_vs_aggressive_risk = _clamp(raw_risk * 2 - 1, -1.0, 1.0)

    # -- 3. control_vs_collaboration -------------------------------------------
    brief_direct = _safe_get(behavioral_metrics, "brief_direct_message_rate")
    warm_rapport = _safe_get(behavioral_metrics, "warm_rapport_rate")

    raw_ctrl = (
        d * 0.45
        - i * 0.30
        - s * 0.20
        + brief_direct * 0.15
        - warm_rapport * 0.15
    )
    control_vs_collaboration = _clamp(raw_ctrl * 2 - 1, -1.0, 1.0)

    # -- 4. short_term_vs_long_term --------------------------------------------
    transition_freq = _safe_get(career_analytics, "transition_frequency")
    mentorship_dropout = _safe_get(behavioral_metrics, "mentorship_dropout_rate")

    raw_horizon = (
        d * 0.30
        + i * 0.20
        - s * 0.30
        - c * 0.20
        + transition_freq * 0.30
        + mentorship_dropout * 0.20
    )
    short_term_vs_long_term = _clamp(raw_horizon * 2 - 1, -1.0, 1.0)

    # -- 5. consistency_score --------------------------------------------------
    contradiction = _safe_get(behavioral_metrics, "contradiction_score")
    latency_cv = _safe_get(behavioral_metrics, "response_latency_cv")
    engagement_var = _safe_get(behavioral_metrics, "engagement_variability")

    raw_consistency = 1.0 - (
        contradiction * 0.50
        + latency_cv * 0.25
        + engagement_var * 0.25
    )
    consistency_score = max(0.0, raw_consistency)

    return PreferenceIndexes(
        stability_vs_growth=round(stability_vs_growth, 4),
        conservative_vs_aggressive_risk=round(conservative_vs_aggressive_risk, 4),
        control_vs_collaboration=round(control_vs_collaboration, 4),
        short_term_vs_long_term=round(short_term_vs_long_term, 4),
        consistency_score=round(consistency_score, 4),
    )
