"""Risk Predictor – compute risk scores across 7 behavioral categories.

Takes DISC scores, preference indexes, career analytics, and behavioral
metrics to produce a risk assessment for each category.  Each score is
normalized to ``[0.0, 1.0]`` and classified into a severity level using
per-category thresholds from the PhxNorth Behavioral Intelligence Spec.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.disc_scorer.preference_inference import PreferenceIndexes
from app.services.disc_scorer.scorer import DISCScores

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity thresholds (from spec)
# ---------------------------------------------------------------------------

RISK_THRESHOLDS: dict[str, dict[str, float]] = {
    "execution_risk": {"yellow": 0.45, "orange": 0.60, "red": 0.75},
    "collaboration_risk": {"yellow": 0.40, "orange": 0.55, "red": 0.70},
    "career_instability_risk": {"yellow": 0.45, "orange": 0.60, "red": 0.75},
    "overconfidence_risk": {"yellow": 0.50, "orange": 0.65, "red": 0.80},
    "avoidance_risk": {"yellow": 0.40, "orange": 0.55, "red": 0.70},
    "leadership_volatility_risk": {"yellow": 0.45, "orange": 0.60, "red": 0.75},
    "behavioral_contradiction_risk": {
        "yellow": 0.30,
        "orange": 0.50,
        "red": 0.70,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_get(mapping: dict[str, Any], key: str, default: float = 0.0) -> float:
    """Extract a float from *mapping*, falling back to *default*.

    Handles ``None`` values and non-numeric entries gracefully.
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


def _clamp01(value: float) -> float:
    """Clamp *value* to ``[0.0, 1.0]``."""
    return max(0.0, min(1.0, value))


def _classify_severity(score: float, category: str) -> str:
    """Map a risk score to a severity level using per-category thresholds.

    Returns one of ``"green"``, ``"yellow"``, ``"orange"``, or ``"red"``.
    """
    thresholds = RISK_THRESHOLDS[category]
    if score >= thresholds["red"]:
        return "red"
    if score >= thresholds["orange"]:
        return "orange"
    if score >= thresholds["yellow"]:
        return "yellow"
    return "green"


# ---------------------------------------------------------------------------
# Individual risk calculators
# ---------------------------------------------------------------------------


def _compute_execution_risk(
    behavioral_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Execution Risk.

    Formula::

        (1 - task_completion_rate) * 0.40
        + min(avg_days_overdue / 10, 1.0) * 0.30
        + response_latency_cv * 0.30
    """
    task_completion_rate = _safe_get(behavioral_metrics, "task_completion_rate")
    avg_days_overdue = _safe_get(behavioral_metrics, "avg_days_overdue")
    response_latency_cv = _safe_get(behavioral_metrics, "response_latency_cv")

    score = _clamp01(
        (1.0 - task_completion_rate) * 0.40
        + min(avg_days_overdue / 10.0, 1.0) * 0.30
        + _clamp01(response_latency_cv) * 0.30
    )

    return {
        "category": "execution_risk",
        "score": round(score, 4),
        "evidence": {
            "task_completion_rate": task_completion_rate,
            "avg_days_overdue": avg_days_overdue,
            "response_latency_cv": response_latency_cv,
        },
    }


def _compute_collaboration_risk(
    behavioral_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Collaboration Risk.

    Formula::

        mentorship_dropout_rate * 0.40
        + variable_engagement_score * 0.35
        + (1 - collaboration_consistency_score) * 0.25
    """
    mentorship_dropout_rate = _safe_get(
        behavioral_metrics, "mentorship_dropout_rate"
    )
    variable_engagement_score = _safe_get(
        behavioral_metrics, "variable_engagement_score"
    )
    collaboration_consistency_score = _safe_get(
        behavioral_metrics, "collaboration_consistency_score"
    )

    score = _clamp01(
        mentorship_dropout_rate * 0.40
        + variable_engagement_score * 0.35
        + (1.0 - collaboration_consistency_score) * 0.25
    )

    return {
        "category": "collaboration_risk",
        "score": round(score, 4),
        "evidence": {
            "mentorship_dropout_rate": mentorship_dropout_rate,
            "variable_engagement_score": variable_engagement_score,
            "collaboration_consistency_score": collaboration_consistency_score,
        },
    }


def _compute_career_instability_risk(
    career_analytics: dict[str, Any],
) -> dict[str, Any]:
    """Career Instability Risk.

    Formula::

        career_volatility_score * 0.45
        + min(transition_frequency, 1.0) * 0.35
        + short_tenure_rate * 0.20
    """
    career_volatility_score = _safe_get(
        career_analytics, "career_volatility_score"
    )
    transition_frequency = _safe_get(career_analytics, "transition_frequency")
    short_tenure_rate = _safe_get(career_analytics, "short_tenure_rate")

    score = _clamp01(
        career_volatility_score * 0.45
        + min(transition_frequency, 1.0) * 0.35
        + short_tenure_rate * 0.20
    )

    return {
        "category": "career_instability_risk",
        "score": round(score, 4),
        "evidence": {
            "career_volatility_score": career_volatility_score,
            "transition_frequency": transition_frequency,
            "short_tenure_rate": short_tenure_rate,
        },
    }


def _compute_overconfidence_risk(
    disc: DISCScores,
    behavioral_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Overconfidence Risk.

    Formula::

        (D / 100) * 0.40
        + (1 - C / 100) * 0.30
        + persistent_task_lateness_rate * 0.30
    """
    d_norm = disc.d / 100.0
    c_norm = disc.c / 100.0
    persistent_task_lateness_rate = _safe_get(
        behavioral_metrics, "persistent_task_lateness_rate"
    )

    score = _clamp01(
        d_norm * 0.40
        + (1.0 - c_norm) * 0.30
        + persistent_task_lateness_rate * 0.30
    )

    return {
        "category": "overconfidence_risk",
        "score": round(score, 4),
        "evidence": {
            "d_score": disc.d,
            "c_score": disc.c,
            "persistent_task_lateness_rate": persistent_task_lateness_rate,
        },
    }


def _compute_avoidance_risk(
    disc: DISCScores,
    behavioral_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Avoidance Risk.

    Formula::

        (S / 100) * 0.25
        + (C / 100) * 0.20
        + slow_deliberate_response_rate * 0.25
        + (1 - project_initiative_rate) * 0.30
    """
    s_norm = disc.s / 100.0
    c_norm = disc.c / 100.0
    slow_deliberate_response_rate = _safe_get(
        behavioral_metrics, "slow_deliberate_response_rate"
    )
    project_initiative_rate = _safe_get(
        behavioral_metrics, "project_initiative_rate"
    )

    score = _clamp01(
        s_norm * 0.25
        + c_norm * 0.20
        + slow_deliberate_response_rate * 0.25
        + (1.0 - project_initiative_rate) * 0.30
    )

    return {
        "category": "avoidance_risk",
        "score": round(score, 4),
        "evidence": {
            "s_score": disc.s,
            "c_score": disc.c,
            "slow_deliberate_response_rate": slow_deliberate_response_rate,
            "project_initiative_rate": project_initiative_rate,
        },
    }


def _compute_leadership_volatility_risk(
    behavioral_metrics: dict[str, Any],
    preferences: PreferenceIndexes,
) -> dict[str, Any]:
    """Leadership Volatility Risk.

    Formula::

        min(shift_magnitude / 0.5, 1.0) * 0.40
        + variable_engagement_score * 0.30
        + (1 - consistency_score) * 0.30
    """
    shift_magnitude = _safe_get(behavioral_metrics, "shift_magnitude")
    variable_engagement_score = _safe_get(
        behavioral_metrics, "variable_engagement_score"
    )
    consistency_score = preferences.consistency_score

    score = _clamp01(
        min(shift_magnitude / 0.5, 1.0) * 0.40
        + variable_engagement_score * 0.30
        + (1.0 - consistency_score) * 0.30
    )

    return {
        "category": "leadership_volatility_risk",
        "score": round(score, 4),
        "evidence": {
            "shift_magnitude": shift_magnitude,
            "variable_engagement_score": variable_engagement_score,
            "consistency_score": consistency_score,
        },
    }


def _compute_behavioral_contradiction_risk(
    behavioral_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Behavioral Contradiction Risk.

    Formula::

        contradiction_score (directly)
    """
    contradiction_score = _safe_get(
        behavioral_metrics, "contradiction_score"
    )

    score = _clamp01(contradiction_score)

    return {
        "category": "behavioral_contradiction_risk",
        "score": round(score, 4),
        "evidence": {
            "contradiction_score": contradiction_score,
        },
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_risk_scores(
    disc: DISCScores,
    preferences: PreferenceIndexes,
    career_analytics: dict[str, Any],
    behavioral_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compute risk scores for each of 7 categories.

    Each category is scored independently using its spec formula.
    Missing or ``None`` metrics default to ``0.0`` so the predictor
    degrades gracefully when data is incomplete.

    Args:
        disc: Computed DISC profile scores (each dimension 0-100).
        preferences: Inferred bipolar preference indexes.
        career_analytics: Career-derived metrics (e.g. from
            :func:`compute_career_analytics`).  Expected keys include
            ``career_volatility_score``, ``transition_frequency``,
            ``short_tenure_rate``.
        behavioral_metrics: Platform behavioral metrics.  Expected keys
            include ``task_completion_rate``, ``avg_days_overdue``,
            ``response_latency_cv``, ``mentorship_dropout_rate``,
            ``variable_engagement_score``,
            ``collaboration_consistency_score``,
            ``persistent_task_lateness_rate``,
            ``slow_deliberate_response_rate``,
            ``project_initiative_rate``, ``shift_magnitude``,
            ``contradiction_score``.

    Returns:
        List of 7 risk assessment dicts, each containing:
            - ``category`` (str): Risk category identifier.
            - ``score`` (float): Normalized risk score in ``[0.0, 1.0]``.
            - ``severity`` (str): ``"green"``/``"yellow"``/``"orange"``/``"red"``.
            - ``evidence`` (dict): Input metrics that contributed to the score.
            - ``is_flagged`` (bool): ``True`` if severity is ``"orange"``
              or ``"red"``.
    """
    raw_results = [
        _compute_execution_risk(behavioral_metrics),
        _compute_collaboration_risk(behavioral_metrics),
        _compute_career_instability_risk(career_analytics),
        _compute_overconfidence_risk(disc, behavioral_metrics),
        _compute_avoidance_risk(disc, behavioral_metrics),
        _compute_leadership_volatility_risk(behavioral_metrics, preferences),
        _compute_behavioral_contradiction_risk(behavioral_metrics),
    ]

    results: list[dict[str, Any]] = []
    for raw in raw_results:
        category = raw["category"]
        score = raw["score"]
        severity = _classify_severity(score, category)

        results.append(
            {
                "category": category,
                "score": score,
                "severity": severity,
                "evidence": raw["evidence"],
                "is_flagged": severity in ("orange", "red"),
            }
        )

    flagged_count = sum(1 for r in results if r["is_flagged"])
    logger.info(
        "Risk prediction complete: %d/%d categories flagged",
        flagged_count,
        len(results),
    )

    return results
