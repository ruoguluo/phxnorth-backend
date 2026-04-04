"""Shift Detector – compares windowed DISC profiles to identify personality shifts.

Compares recent (30-day) vs baseline (90-day) DISC profiles to detect
situational, structural, or transitional personality changes.
"""

from __future__ import annotations

import logging
import math

from app.services.disc_scorer.scorer import DISCScores

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHIFT_THRESHOLD: float = 0.25
"""Minimum Euclidean distance (normalized 0-1) to flag a meaningful shift."""

STRUCTURAL_THRESHOLD: float = 0.40
"""Distance above which a shift is considered potentially enduring."""

DIMENSIONS: tuple[str, ...] = ("D", "I", "S", "C")

# Maximum possible Euclidean distance between two DISC vectors:
# sqrt((100-0)^2 * 4) = 200.0
_MAX_DISTANCE: float = 200.0

# Threshold for lifetime-recent alignment indicating structural shift
_LIFETIME_ALIGNMENT_THRESHOLD: float = 0.15

# ---------------------------------------------------------------------------
# Interpretation mapping
# ---------------------------------------------------------------------------

_INCREASE_INTERPRETATIONS: dict[str, str] = {
    "D": "Elevated urgency or assertiveness",
    "I": "Increased social engagement",
    "S": "Seeking stability",
    "C": "Increased precision focus",
}

_DECREASE_INTERPRETATIONS: dict[str, str] = {
    "D": "Reduced drive — possible burnout",
    "I": "Social withdrawal",
    "S": "Reduced patience — restlessness",
    "C": "Reduced detail attention",
}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def compute_disc_distance(a: DISCScores, b: DISCScores) -> float:
    """Euclidean distance between two DISC vectors, normalized to 0-1.

    Max possible distance = ~200 (from (0,0,0,0) vs (100,100,100,100)),
    so the result is divided by 200 to land in ``[0.0, 1.0]``.

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


def _build_shifted_dimensions(
    recent: DISCScores,
    baseline: DISCScores,
) -> dict[str, float]:
    """Compute per-dimension signed deltas (recent - baseline).

    Args:
        recent: The 30-day windowed profile.
        baseline: The 90-day windowed profile.

    Returns:
        Dict mapping dimension letter to signed delta.
    """
    return {
        dim: round(_get_score(recent, dim) - _get_score(baseline, dim), 2)
        for dim in DIMENSIONS
    }


def _build_interpretation(shifted_dimensions: dict[str, float]) -> str:
    """Build a human-readable interpretation of the dimension shifts.

    Only dimensions with |delta| > 5.0 (on the 0-100 scale) are
    mentioned to avoid noisy micro-shifts.

    Args:
        shifted_dimensions: Per-dimension signed deltas.

    Returns:
        Semicolon-separated interpretation string, or a stable message.
    """
    parts: list[str] = []
    for dim, delta in shifted_dimensions.items():
        if abs(delta) <= 5.0:
            continue
        if delta > 0:
            parts.append(_INCREASE_INTERPRETATIONS[dim])
        else:
            parts.append(_DECREASE_INTERPRETATIONS[dim])

    return "; ".join(parts) if parts else "Profile is stable across windows"


def detect_personality_shift(
    profiles: dict[str, DISCScores],
) -> dict:
    """Compare 30-day vs 90-day profiles to detect personality shifts.

    Shift classification logic:
        1. If magnitude < ``SHIFT_THRESHOLD`` (0.25): **stable** — no
           meaningful shift detected.
        2. If a ``"lifetime"`` profile exists and its distance to the
           recent profile is < 0.15: **structural** — the recent profile
           has converged with the long-term baseline, suggesting an
           enduring change.
        3. If magnitude < ``STRUCTURAL_THRESHOLD`` (0.40): **situational**
           — a short-term adaptation, likely context-driven.
        4. Otherwise: **transitional** — the person is actively changing.

    Args:
        profiles: Dict with at least keys ``"30d"`` and ``"90d"``, each
            mapping to a :class:`DISCScores`.  An optional ``"lifetime"``
            key refines the classification.

    Returns:
        Dict with keys:
            - ``shift_detected``: bool
            - ``magnitude``: float (0-1)
            - ``shift_type``: ``"stable"`` | ``"situational"``
              | ``"structural"`` | ``"transitional"``
            - ``shifted_dimensions``: dict mapping dimension to signed delta
            - ``interpretation``: human-readable explanation
    """
    recent = profiles["30d"]
    baseline = profiles["90d"]

    magnitude = compute_disc_distance(recent, baseline)
    shifted_dimensions = _build_shifted_dimensions(recent, baseline)

    # Classification
    if magnitude < SHIFT_THRESHOLD:
        shift_type = "stable"
        shift_detected = False
    else:
        shift_detected = True

        # Check lifetime alignment for structural classification
        lifetime = profiles.get("lifetime")
        if lifetime is not None:
            lifetime_recent_distance = compute_disc_distance(lifetime, recent)
            if lifetime_recent_distance < _LIFETIME_ALIGNMENT_THRESHOLD:
                shift_type = "structural"
            elif magnitude < STRUCTURAL_THRESHOLD:
                shift_type = "situational"
            else:
                shift_type = "transitional"
        else:
            # Without lifetime data, fall back to magnitude-only classification
            if magnitude < STRUCTURAL_THRESHOLD:
                shift_type = "situational"
            else:
                shift_type = "transitional"

    interpretation = _build_interpretation(shifted_dimensions)

    logger.info(
        "Shift detection: magnitude=%.3f type=%s detected=%s",
        magnitude,
        shift_type,
        shift_detected,
    )

    return {
        "shift_detected": shift_detected,
        "magnitude": round(magnitude, 4),
        "shift_type": shift_type,
        "shifted_dimensions": shifted_dimensions,
        "interpretation": interpretation,
    }
