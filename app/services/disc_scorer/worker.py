"""DISC Scorer Worker – orchestrates scoring, windowed profiles, shift detection,
and preference inference into a single unified pipeline.

This is the top-level entry point for computing a complete DISC profile for a
user.  It delegates to the specialised sub-modules and assembles the result
dict expected by upstream consumers.
"""

from __future__ import annotations

import logging
from dataclasses import asdict

from app.services.disc_scorer.preference_inference import (
    PreferenceIndexes,
    infer_preferences,
)
from app.services.disc_scorer.scorer import DISCScores, WeightedSignal
from app.services.disc_scorer.shift_detector import detect_personality_shift
from app.services.disc_scorer.windows import compute_windowed_profiles

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRIMARY_WINDOW: str = "90d"
"""Window label used as the authoritative / primary profile."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _disc_scores_to_dict(scores: DISCScores) -> dict:
    """Convert a :class:`DISCScores` to a JSON-friendly dict.

    The ``computed_at`` datetime is serialised to an ISO-8601 string.
    """
    data = asdict(scores)
    data["computed_at"] = scores.computed_at.isoformat()
    return data


def _preference_indexes_to_dict(prefs: PreferenceIndexes) -> dict:
    """Convert a :class:`PreferenceIndexes` to a plain dict."""
    return asdict(prefs)


def _empty_result(*, error: str | None = None) -> dict:
    """Return a well-formed result dict when no scoring is possible."""
    return {
        "profiles": {},
        "shift": {},
        "preferences": {},
        "signal_count": 0,
        "dominant": None,
        "secondary": None,
        "confidence": 0.0,
        "success": error is None,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def compute_user_disc_profile(
    signals: list[WeightedSignal],
    career_analytics: dict | None = None,
    behavioral_metrics: dict | None = None,
    user_id: str | None = None,
) -> dict:
    """Compute complete DISC profile for a user.

    Orchestrates windowed scoring, shift detection, and preference inference
    into a single result dict.

    Args:
        signals: All weighted signals (CV + platform).
        career_analytics: Career analytics dict (for preference inference).
        behavioral_metrics: Behavioral metrics dict (for preference inference).
        user_id: Optional user ID (for logging / tracing).

    Returns:
        dict with keys:
            - ``profiles``: dict[str, dict] – windowed profiles (30d, 90d, lifetime)
            - ``shift``: dict – shift detection result
            - ``preferences``: dict – preference indexes
            - ``signal_count``: int
            - ``dominant``: str – primary DISC dimension
            - ``secondary``: str | None
            - ``confidence``: float
            - ``success``: bool
            - ``error``: str | None
    """
    log_prefix = f"[user={user_id}] " if user_id else ""

    # ------------------------------------------------------------------
    # Guard: no signals
    # ------------------------------------------------------------------
    if not signals:
        logger.info("%sNo signals provided – returning empty profile", log_prefix)
        return _empty_result()

    try:
        # ------------------------------------------------------------------
        # 1. Windowed DISC profiles (30d, 90d, lifetime)
        # ------------------------------------------------------------------
        logger.info(
            "%sComputing windowed profiles from %d signals",
            log_prefix,
            len(signals),
        )
        windowed: dict[str, DISCScores] = compute_windowed_profiles(signals)

        # ------------------------------------------------------------------
        # 2. Primary profile (90d)
        # ------------------------------------------------------------------
        primary: DISCScores = windowed[PRIMARY_WINDOW]

        # ------------------------------------------------------------------
        # 3. Shift detection (compares 30d vs 90d, with lifetime context)
        # ------------------------------------------------------------------
        logger.info("%sRunning shift detection", log_prefix)
        shift_result: dict = detect_personality_shift(windowed)

        # ------------------------------------------------------------------
        # 4. Preference inference
        # ------------------------------------------------------------------
        prefs_dict: dict = {}
        ca = career_analytics or {}
        bm = behavioral_metrics or {}

        if ca or bm:
            logger.info("%sInferring preferences", log_prefix)
            prefs: PreferenceIndexes = infer_preferences(primary, ca, bm)
            prefs_dict = _preference_indexes_to_dict(prefs)
        else:
            logger.info(
                "%sSkipping preference inference (no career/behavioral data)",
                log_prefix,
            )

        # ------------------------------------------------------------------
        # 5. Assemble result
        # ------------------------------------------------------------------
        profiles_dict: dict[str, dict] = {
            label: _disc_scores_to_dict(scores)
            for label, scores in windowed.items()
        }

        result: dict = {
            "profiles": profiles_dict,
            "shift": shift_result,
            "preferences": prefs_dict,
            "signal_count": primary.signal_count,
            "dominant": primary.dominant,
            "secondary": primary.secondary,
            "confidence": primary.confidence,
            "success": True,
            "error": None,
        }

        logger.info(
            "%sProfile complete: dominant=%s secondary=%s confidence=%.3f signals=%d",
            log_prefix,
            primary.dominant,
            primary.secondary,
            primary.confidence,
            primary.signal_count,
        )

        return result

    except Exception:
        logger.exception("%sFailed to compute DISC profile", log_prefix)
        return _empty_result(error="Internal error during DISC profile computation")
