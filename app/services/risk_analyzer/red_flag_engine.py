"""Red Flag Engine – generate immutable audit trail entries from risk data.

Transforms risk assessments and contradiction analysis into discrete red flag
events.  Each flag is an immutable record with a type, severity, human-readable
description, and supporting metadata.

Red flags are generated when:
    * A risk assessment has severity ``"orange"`` or ``"red"``.
    * The overall contradiction score exceeds 0.50 (high) or 0.70 (severe).
    * Individual DISC dimensions are flagged by the contradiction detector.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_HIGH_CONTRADICTION_THRESHOLD: float = 0.50
_SEVERE_CONTRADICTION_THRESHOLD: float = 0.70

# Map risk severity → flag_type prefix
_RISK_SEVERITY_PREFIX: dict[str, str] = {
    "orange": "high",
    "red": "critical",
}

# Human-readable severity labels for risk-based flags
_RISK_SEVERITY_DESCRIPTION: dict[str, str] = {
    "orange": "elevated",
    "red": "critical",
}

# Human-readable labels for DISC dimensions
_DIMENSION_LABELS: dict[str, str] = {
    "D": "Dominance",
    "I": "Influence",
    "S": "Steadiness",
    "C": "Conscientiousness",
}


# ---------------------------------------------------------------------------
# Internal generators
# ---------------------------------------------------------------------------


def _flags_from_risk_assessments(
    risk_assessments: list[dict[str, Any]],
    user_id: str | None,
) -> list[dict[str, Any]]:
    """Generate red flags from risk assessments with orange/red severity."""
    flags: list[dict[str, Any]] = []

    for assessment in risk_assessments:
        severity = assessment.get("severity", "green")
        if severity not in _RISK_SEVERITY_PREFIX:
            continue

        category: str = assessment.get("category", "unknown")
        score: float = assessment.get("score", 0.0)
        prefix = _RISK_SEVERITY_PREFIX[severity]
        desc_label = _RISK_SEVERITY_DESCRIPTION[severity]

        # e.g. "high_execution_risk" or "critical_collaboration_risk"
        flag_type = f"{prefix}_{category}"

        # Human-readable category: "execution_risk" → "execution risk"
        readable_category = category.replace("_", " ")

        flags.append(
            {
                "flag_type": flag_type,
                "severity": severity,
                "description": (
                    f"{desc_label.capitalize()} {readable_category} detected "
                    f"(score: {score:.2f})"
                ),
                "metadata": {
                    "category": category,
                    "score": score,
                    "evidence": assessment.get("evidence", {}),
                },
                "user_id": user_id,
            }
        )

    return flags


def _flags_from_contradiction(
    contradiction_result: dict[str, Any],
    user_id: str | None,
) -> list[dict[str, Any]]:
    """Generate red flags from contradiction analysis.

    Produces up to three classes of flags:
    1. Overall high/severe contradiction (score thresholds).
    2. Per-dimension contradiction flags for each flagged dimension.
    """
    flags: list[dict[str, Any]] = []

    score: float = contradiction_result.get("contradiction_score", 0.0)
    contradiction_type: str = contradiction_result.get(
        "contradiction_type", "unknown"
    )
    severity_tier: str = contradiction_result.get("severity_tier", "consistent")
    flagged_dimensions: dict[str, float] = contradiction_result.get(
        "flagged_dimensions", {}
    )

    # --- Overall contradiction flags ---

    if score > _SEVERE_CONTRADICTION_THRESHOLD:
        flags.append(
            {
                "flag_type": "severe_contradiction",
                "severity": "red",
                "description": (
                    f"Severe contradiction between CV and platform profiles "
                    f"(score: {score:.2f}, type: {contradiction_type})"
                ),
                "metadata": {
                    "contradiction_score": score,
                    "contradiction_type": contradiction_type,
                    "severity_tier": severity_tier,
                },
                "user_id": user_id,
            }
        )
    elif score > _HIGH_CONTRADICTION_THRESHOLD:
        flags.append(
            {
                "flag_type": "high_contradiction",
                "severity": "orange",
                "description": (
                    f"High contradiction between CV and platform profiles "
                    f"(score: {score:.2f}, type: {contradiction_type})"
                ),
                "metadata": {
                    "contradiction_score": score,
                    "contradiction_type": contradiction_type,
                    "severity_tier": severity_tier,
                },
                "user_id": user_id,
            }
        )

    # --- Per-dimension contradiction flags ---

    for dim, gap in flagged_dimensions.items():
        dim_label = _DIMENSION_LABELS.get(dim, dim)
        dim_key = dim.lower()

        flags.append(
            {
                "flag_type": f"dimension_contradiction_{dim_key}",
                "severity": "yellow",
                "description": (
                    f"{dim_label} ({dim}) dimension shows significant "
                    f"divergence between CV and platform (gap: {gap:.1f} points)"
                ),
                "metadata": {
                    "dimension": dim,
                    "gap": gap,
                    "contradiction_score": score,
                },
                "user_id": user_id,
            }
        )

    return flags


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_red_flags(
    risk_assessments: list[dict],
    contradiction_result: dict,
    user_id: str | None = None,
) -> list[dict]:
    """Generate red flag events from risk assessments and contradiction analysis.

    Red flags are immutable audit trail entries.  Each flag carries enough
    context to reconstruct *why* it was raised without needing access to the
    original input data.

    **Risk-based flags** are emitted when a risk assessment has severity
    ``"orange"`` or ``"red"``:

    * ``high_{category}_risk`` — for orange severity.
    * ``critical_{category}_risk`` — for red severity.

    **Contradiction-based flags** are emitted based on the overall score
    and per-dimension analysis:

    * ``high_contradiction`` — score in ``(0.50, 0.70]``.
    * ``severe_contradiction`` — score ``> 0.70``.
    * ``dimension_contradiction_{dim}`` — for each flagged DISC dimension.

    Args:
        risk_assessments: List of risk assessment dicts as produced by
            :func:`~app.services.risk_analyzer.risk_predictor.compute_risk_scores`.
            Each dict must contain at minimum ``category``, ``score``, and
            ``severity`` keys.
        contradiction_result: Contradiction analysis dict as produced by
            :func:`~app.services.risk_analyzer.contradiction_detector.compute_contradiction_score`.
            Expected keys: ``contradiction_score``, ``contradiction_type``,
            ``severity_tier``, ``flagged_dimensions``.
        user_id: Optional user identifier to attach to every flag event.

    Returns:
        List of red flag event dicts, each with:
            - ``flag_type`` (str): Machine-readable flag identifier.
            - ``severity`` (str): ``"yellow"``, ``"orange"``, or ``"red"``.
            - ``description`` (str): Human-readable explanation.
            - ``metadata`` (dict): Evidence and context for the flag.
            - ``user_id`` (str | None): The user this flag applies to.
    """
    flags: list[dict[str, Any]] = []

    flags.extend(_flags_from_risk_assessments(risk_assessments, user_id))
    flags.extend(_flags_from_contradiction(contradiction_result, user_id))

    logger.info(
        "Red flag generation complete: %d flags emitted (user=%s)",
        len(flags),
        user_id,
    )

    return flags
