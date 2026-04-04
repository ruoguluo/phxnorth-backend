"""Risk Analyzer Worker – orchestrates contradiction detection, risk prediction,
and red flag generation into a single unified pipeline.

This is the top-level entry point for computing a complete risk analysis for a
user.  It delegates to the specialised sub-modules and assembles the result
dict expected by upstream consumers.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.disc_scorer.preference_inference import PreferenceIndexes
from app.services.disc_scorer.scorer import DISCScores
from app.services.risk_analyzer.contradiction_detector import (
    compute_contradiction_score,
)
from app.services.risk_analyzer.red_flag_engine import generate_red_flags
from app.services.risk_analyzer.risk_predictor import compute_risk_scores

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity ordering (highest → lowest)
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[str, int] = {
    "red": 3,
    "orange": 2,
    "yellow": 1,
    "green": 0,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_result(*, error: str | None = None) -> dict[str, Any]:
    """Return a well-formed result dict when no analysis is possible."""
    return {
        "contradiction": {},
        "risk_assessments": [],
        "red_flags": [],
        "overall_risk_level": "green",
        "flagged_count": 0,
        "success": error is None,
        "error": error,
    }


def _highest_severity(assessments: list[dict[str, Any]]) -> str:
    """Determine the highest severity level across all risk assessments.

    Args:
        assessments: List of risk assessment dicts, each with a ``severity`` key.

    Returns:
        The highest severity string: ``"red"``, ``"orange"``, ``"yellow"``,
        or ``"green"`` (default when *assessments* is empty).
    """
    if not assessments:
        return "green"

    best = "green"
    best_rank = 0
    for assessment in assessments:
        sev = assessment.get("severity", "green")
        rank = _SEVERITY_ORDER.get(sev, 0)
        if rank > best_rank:
            best_rank = rank
            best = sev
    return best


def _build_default_preferences() -> PreferenceIndexes:
    """Build neutral preferences when none are provided.

    All bipolar indexes default to ``0.0`` (neutral) and consistency to
    ``0.5`` (moderate).
    """
    return PreferenceIndexes(
        stability_vs_growth=0.0,
        conservative_vs_aggressive_risk=0.0,
        control_vs_collaboration=0.0,
        short_term_vs_long_term=0.0,
        consistency_score=0.5,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def analyze_user_risk(
    cv_profile: DISCScores | None,
    platform_profile: DISCScores | None,
    disc_profile: DISCScores,
    preferences: PreferenceIndexes | None = None,
    career_analytics: dict | None = None,
    behavioral_metrics: dict | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Complete risk analysis for a user.

    Orchestrates three stages:

    1. **Contradiction detection** – compare CV vs platform DISC profiles
       (skipped if either profile is absent).
    2. **Risk prediction** – compute 7 risk category scores from the DISC
       profile and supporting metrics.
    3. **Red flag generation** – convert risk assessments and contradiction
       data into actionable red flag events.

    Args:
        cv_profile: DISC scores derived from CV analysis (may be ``None``).
        platform_profile: DISC scores from platform behaviour (may be ``None``).
        disc_profile: Authoritative DISC profile (e.g. the 90-day window).
        preferences: Bipolar preference indexes.  Falls back to neutral
            defaults when ``None``.
        career_analytics: Career-derived metrics dict.
        behavioral_metrics: Platform behavioural metrics dict.
        user_id: Optional user ID for logging / tracing.

    Returns:
        dict with keys:
            - ``contradiction``: dict – contradiction analysis result
            - ``risk_assessments``: list[dict] – 7 risk category results
            - ``red_flags``: list[dict] – generated red flag events
            - ``overall_risk_level``: str – highest severity across all assessments
            - ``flagged_count``: int – number of flagged (orange/red) assessments
            - ``success``: bool
            - ``error``: str | None
    """
    log_prefix = f"[user={user_id}] " if user_id else ""

    try:
        # ------------------------------------------------------------------
        # 1. Contradiction detection (optional – requires both profiles)
        # ------------------------------------------------------------------
        contradiction_result: dict[str, Any] = {}

        if cv_profile is not None and platform_profile is not None:
            logger.info(
                "%sRunning contradiction detection (CV vs platform)",
                log_prefix,
            )
            contradiction_result = compute_contradiction_score(
                cv_profile, platform_profile
            )
        else:
            logger.info(
                "%sSkipping contradiction detection "
                "(cv_profile=%s, platform_profile=%s)",
                log_prefix,
                "present" if cv_profile else "absent",
                "present" if platform_profile else "absent",
            )

        # ------------------------------------------------------------------
        # 2. Risk prediction (7 categories)
        # ------------------------------------------------------------------
        effective_preferences = preferences or _build_default_preferences()
        ca = career_analytics or {}
        bm = behavioral_metrics or {}

        # Inject contradiction score into behavioral_metrics so the
        # behavioral_contradiction_risk calculator can use it.
        if contradiction_result and "contradiction_score" in contradiction_result:
            bm = {**bm, "contradiction_score": contradiction_result["contradiction_score"]}

        logger.info("%sComputing risk scores across 7 categories", log_prefix)
        risk_assessments: list[dict[str, Any]] = compute_risk_scores(
            disc_profile,
            effective_preferences,
            ca,
            bm,
        )

        # ------------------------------------------------------------------
        # 3. Red flag generation
        # ------------------------------------------------------------------
        logger.info("%sGenerating red flags", log_prefix)
        red_flags: list[dict[str, Any]] = generate_red_flags(
            risk_assessments, contradiction_result, user_id=user_id
        )

        # ------------------------------------------------------------------
        # 4. Aggregate summary
        # ------------------------------------------------------------------
        overall_risk_level = _highest_severity(risk_assessments)
        flagged_count = sum(
            1 for r in risk_assessments if r.get("is_flagged", False)
        )

        result: dict[str, Any] = {
            "contradiction": contradiction_result,
            "risk_assessments": risk_assessments,
            "red_flags": red_flags,
            "overall_risk_level": overall_risk_level,
            "flagged_count": flagged_count,
            "success": True,
            "error": None,
        }

        logger.info(
            "%sRisk analysis complete: overall=%s flagged=%d/%d red_flags=%d",
            log_prefix,
            overall_risk_level,
            flagged_count,
            len(risk_assessments),
            len(red_flags),
        )

        return result

    except Exception:
        logger.exception("%sFailed to complete risk analysis", log_prefix)
        return _empty_result(error="Internal error during risk analysis")
