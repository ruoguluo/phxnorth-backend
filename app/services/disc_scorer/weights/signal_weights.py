"""Signal weight library mapping signal types to DISC dimension weights.

Each signal type has weights for all four DISC dimensions (D, I, S, C),
ranging from -1.0 to +1.0. Positive weights indicate the signal supports
that dimension; negative weights indicate it opposes that dimension.

Signals are grouped into two categories:
- CV / Career signals: derived from CV parsing and career history analysis
- Platform Behavioral signals: derived from real-time platform interactions
"""

import enum
from typing import TypedDict


class DISCWeights(TypedDict):
    """Weight vector for a single signal across all four DISC dimensions."""

    D: float
    I: float
    S: float
    C: float


class SignalCategory(str, enum.Enum):
    """Categories of behavioral signals."""

    CV_CAREER = "cv_career"
    PLATFORM_BEHAVIORAL = "platform_behavioral"


# ---------------------------------------------------------------------------
# CV / Career Signals
# ---------------------------------------------------------------------------

_CV_CAREER_SIGNALS: dict[str, DISCWeights] = {
    "short_tenure_detected": {"D": +0.60, "I": +0.20, "S": -0.50, "C": -0.30},
    "rapid_career_transitions": {"D": +0.50, "I": +0.30, "S": -0.60, "C": -0.20},
    "long_tenure": {"D": -0.30, "I": +0.10, "S": +0.70, "C": +0.30},
    "cross_industry_transition": {"D": +0.50, "I": +0.30, "S": -0.30, "C": -0.10},
    "consistent_upward_progression": {"D": +0.70, "I": +0.20, "S": +0.10, "C": +0.30},
    "lateral_dominant_pattern": {"D": -0.20, "I": +0.10, "S": +0.40, "C": +0.50},
    "founder_experience": {"D": +0.80, "I": +0.40, "S": -0.20, "C": +0.10},
    "career_gap_detected": {"D": -0.10, "I": -0.10, "S": +0.20, "C": +0.20},
    "downward_transition": {"D": -0.30, "I": -0.10, "S": +0.30, "C": +0.20},
    "high_industry_diversity": {"D": +0.40, "I": +0.40, "S": -0.30, "C": -0.10},
    "mono_industry_career": {"D": -0.20, "I": 0.00, "S": +0.50, "C": +0.40},
}

# ---------------------------------------------------------------------------
# Platform Behavioral Signals
# ---------------------------------------------------------------------------

_PLATFORM_BEHAVIORAL_SIGNALS: dict[str, DISCWeights] = {
    # Response patterns
    "fast_response_latency": {"D": +0.40, "I": +0.40, "S": -0.10, "C": -0.20},
    "slow_deliberate_response": {"D": -0.30, "I": -0.20, "S": +0.30, "C": +0.50},
    "inconsistent_response_latency": {"D": +0.20, "I": +0.30, "S": -0.40, "C": -0.30},
    # Communication preferences
    "prefers_video_voice": {"D": +0.30, "I": +0.60, "S": +0.10, "C": -0.20},
    "prefers_text_email": {"D": +0.20, "I": -0.20, "S": +0.20, "C": +0.50},
    # Message style
    "brief_direct_messages": {"D": +0.70, "I": +0.10, "S": -0.10, "C": -0.30},
    "detailed_thorough_messages": {"D": -0.20, "I": -0.10, "S": +0.20, "C": +0.70},
    "warm_rapport_messages": {"D": -0.20, "I": +0.70, "S": +0.30, "C": -0.10},
    # Task discipline
    "high_task_discipline": {"D": +0.20, "I": -0.10, "S": +0.30, "C": +0.70},
    "low_task_discipline": {"D": +0.30, "I": +0.40, "S": -0.30, "C": -0.60},
    "early_task_submission": {"D": +0.30, "I": -0.10, "S": +0.10, "C": +0.60},
    "persistent_task_lateness": {"D": +0.20, "I": +0.30, "S": -0.20, "C": -0.70},
    # Mentorship engagement
    "mentorship_dropout": {"D": +0.40, "I": +0.20, "S": -0.50, "C": -0.30},
    "long_mentorship_engagement": {"D": -0.10, "I": +0.20, "S": +0.60, "C": +0.30},
    # Question patterns
    "deepening_questions_over_time": {"D": +0.20, "I": +0.10, "S": +0.20, "C": +0.70},
    "surface_questions_only": {"D": +0.40, "I": +0.30, "S": -0.10, "C": -0.40},
    "strategic_abstract_questions": {"D": +0.50, "I": +0.30, "S": -0.10, "C": -0.10},
    "process_detail_questions": {"D": -0.20, "I": -0.20, "S": +0.40, "C": +0.60},
    # Mentor selection
    "selects_authority_mentor": {"D": +0.50, "I": +0.20, "S": +0.10, "C": +0.20},
    "selects_peer_style_mentor": {"D": -0.20, "I": +0.50, "S": +0.40, "C": +0.10},
    "careful_mentor_selection": {"D": -0.20, "I": -0.10, "S": +0.20, "C": +0.70},
    "quick_impulsive_mentor_selection": {"D": +0.60, "I": +0.40, "S": -0.20, "C": -0.40},
    # Collaboration patterns
    "high_collaboration_consistency": {"D": +0.10, "I": +0.30, "S": +0.60, "C": +0.30},
    "variable_engagement_pattern": {"D": +0.40, "I": +0.30, "S": -0.50, "C": -0.20},
    # Project engagement
    "project_self_join": {"D": +0.60, "I": +0.30, "S": 0.00, "C": +0.10},
    "project_early_dropout": {"D": +0.30, "I": +0.20, "S": -0.40, "C": -0.30},
    # Session depth
    "high_session_depth_score": {"D": +0.10, "I": +0.20, "S": +0.20, "C": +0.70},
}

# ---------------------------------------------------------------------------
# Combined registry
# ---------------------------------------------------------------------------

SIGNAL_WEIGHTS: dict[str, DISCWeights] = {
    **_CV_CAREER_SIGNALS,
    **_PLATFORM_BEHAVIORAL_SIGNALS,
}

# Internal lookup for category membership
_SIGNAL_CATEGORY: dict[str, SignalCategory] = {
    **{k: SignalCategory.CV_CAREER for k in _CV_CAREER_SIGNALS},
    **{k: SignalCategory.PLATFORM_BEHAVIORAL for k in _PLATFORM_BEHAVIORAL_SIGNALS},
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get_signal_weight(signal_type: str) -> DISCWeights | None:
    """Look up the DISC weight vector for a signal type.

    Args:
        signal_type: Identifier for the signal (e.g. ``"founder_experience"``).

    Returns:
        A :class:`DISCWeights` dict with keys ``D``, ``I``, ``S``, ``C``,
        or ``None`` if the signal type is not recognised.
    """
    return SIGNAL_WEIGHTS.get(signal_type)


def get_all_signal_types() -> list[str]:
    """Return a sorted list of every registered signal type.

    Returns:
        Alphabetically sorted signal type identifiers.
    """
    return sorted(SIGNAL_WEIGHTS.keys())


def get_cv_signals() -> dict[str, DISCWeights]:
    """Return the weight map for CV / career signals only.

    Returns:
        Dict mapping CV signal types to their DISC weight vectors.
    """
    return dict(_CV_CAREER_SIGNALS)


def get_platform_signals() -> dict[str, DISCWeights]:
    """Return the weight map for platform behavioral signals only.

    Returns:
        Dict mapping platform signal types to their DISC weight vectors.
    """
    return dict(_PLATFORM_BEHAVIORAL_SIGNALS)


def get_signals_by_category(category: SignalCategory) -> dict[str, DISCWeights]:
    """Return signals filtered by category.

    Args:
        category: The :class:`SignalCategory` to filter on.

    Returns:
        Dict mapping signal types in the requested category to their
        DISC weight vectors.
    """
    return {
        signal_type: SIGNAL_WEIGHTS[signal_type]
        for signal_type, cat in _SIGNAL_CATEGORY.items()
        if cat is category
    }
