"""Platform signal extraction from behavioral events to DISC signals.

Translates validated behavioral events into weighted DISC signals by
looking up the event-to-signal mappings and applying context modifiers
derived from event payloads.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.signal_extractor.mappings.event_mappings import (
    apply_context_modifier,
    get_event_mapping,
)
from app.services.signal_extractor.validation.event_validator import validate_event

logger = logging.getLogger(__name__)

# ---- context detection rules ------------------------------------------------
# Each rule is a callable (event_type, normalized_event) -> str | None
# returning the modifier name when the condition holds.


def _detect_fast_response(event: dict[str, Any]) -> str | None:
    """MESSAGE_RESPONDED with latency_ms < 300."""
    latency = event.get("payload", {}).get("latency_ms") or event.get("latency_ms")
    if latency is not None and latency < 300:
        return "fast_response"
    return None


def _detect_slow_response(event: dict[str, Any]) -> str | None:
    """MESSAGE_RESPONDED with latency_ms > 3 600 000 (1 hour)."""
    latency = event.get("payload", {}).get("latency_ms") or event.get("latency_ms")
    if latency is not None and latency > 3_600_000:
        return "slow_response"
    return None


def _detect_task_timing(event: dict[str, Any]) -> str | None:
    """TASK_COMPLETED: compare completed_at vs deadline in payload."""
    payload = event.get("payload", {})
    deadline_raw = payload.get("deadline")
    completed_raw = payload.get("completed_at") or event.get("created_at")

    if deadline_raw is None:
        return None

    deadline = _parse_dt(deadline_raw)
    completed = _parse_dt(completed_raw)
    if deadline is None or completed is None:
        return None

    diff = (deadline - completed).total_seconds()
    # More than 1 hour early
    if diff > 3600:
        return "early_completion"
    # Late: completed after deadline
    if diff < 0:
        return "late"
    return "on_time"


def _detect_answer_speed(event: dict[str, Any]) -> str | None:
    """ASSESSMENT_QUESTION_ANSWER: duration_seconds in payload."""
    payload = event.get("payload", {})
    duration = payload.get("duration_seconds")
    if duration is None:
        return None
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        return None
    if duration < 10:
        return "quick_answer"
    if duration > 60:
        return "thoughtful_answer"
    return None


def _detect_session_length(event: dict[str, Any]) -> str | None:
    """SESSION_END: duration_minutes in payload."""
    payload = event.get("payload", {})
    duration = payload.get("duration_minutes")
    if duration is None:
        return None
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        return None
    if duration > 30:
        return "long_session"
    if duration < 5:
        return "short_session"
    return None


def _detect_scroll_depth(event: dict[str, Any]) -> str | None:
    """SCROLL: scroll_depth_percent in payload."""
    payload = event.get("payload", {})
    depth = payload.get("scroll_depth_percent")
    if depth is None:
        return None
    try:
        depth = float(depth)
    except (TypeError, ValueError):
        return None
    if depth > 80:
        return "deep_scroll"
    if depth < 20:
        return "shallow_scroll"
    return None


def _detect_question_detail(event: dict[str, Any]) -> str | None:
    """QUESTION_POSTED: length of question_text in payload."""
    payload = event.get("payload", {})
    text = payload.get("question_text", "")
    if not isinstance(text, str):
        return None
    length = len(text)
    if length > 100:
        return "detailed_question"
    if length < 30:
        return "brief_question"
    return None


# Map event_type -> list of detector functions
_CONTEXT_DETECTORS: dict[str, list[Any]] = {
    "MESSAGE_RESPONDED": [_detect_fast_response, _detect_slow_response],
    "TASK_COMPLETED": [_detect_task_timing],
    "ASSESSMENT_QUESTION_ANSWER": [_detect_answer_speed],
    "SESSION_END": [_detect_session_length],
    "SCROLL": [_detect_scroll_depth],
    "QUESTION_POSTED": [_detect_question_detail],
}


# ---- helpers ----------------------------------------------------------------


def _parse_dt(value: Any) -> datetime | None:
    """Best-effort parse to a timezone-aware datetime."""
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


def _detect_context_modifiers(event_type: str, event: dict[str, Any]) -> list[str]:
    """Detect applicable context modifiers from event payload.

    Returns a list of modifier names (may be empty).
    """
    detectors = _CONTEXT_DETECTORS.get(event_type, [])
    modifiers: list[str] = []
    for detector in detectors:
        result = detector(event)
        if result is not None:
            modifiers.append(result)
    return modifiers


def _extract_signals_from_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract DISC signals from a single validated/normalized event.

    Returns a list of signal dicts with keys:
    - dimension: str (D/I/S/C)
    - weight: float
    - timestamp: str (ISO-8601)
    - evidence: dict with event_type, context, modifier (if any)
    - event_type: str
    """
    event_type = event["event_type"]
    mapping = get_event_mapping(event_type)
    if mapping is None:
        return []

    base_signals: list[dict[str, Any]] = [
        s.copy() for s in mapping.get("signals", [])
    ]

    # Detect and apply context modifiers
    modifiers = _detect_context_modifiers(event_type, event)

    signals = base_signals
    applied_modifiers: list[str] = []
    for modifier_name in modifiers:
        signals = apply_context_modifier(event_type, modifier_name, signals)
        applied_modifiers.append(modifier_name)

    # Build timestamp from normalized event
    created_at = event.get("created_at")
    if isinstance(created_at, datetime):
        ts_iso = created_at.isoformat()
    elif isinstance(created_at, str):
        ts_iso = created_at
    else:
        ts_iso = datetime.now(timezone.utc).isoformat()

    # Build output signal dicts
    result: list[dict[str, Any]] = []
    for sig in signals:
        signal_id = str(uuid.uuid4())
        result.append({
            "id": signal_id,
            "dimension": sig["dimension"],
            "weight": round(sig["weight"], 4),
            "timestamp": ts_iso,
            "event_type": event_type,
            "evidence": {
                "event_type": event_type,
                "context": sig.get("context", ""),
                "modifiers_applied": applied_modifiers,
                "user_id": event.get("user_id", ""),
            },
        })

    return result


# ---- public API --------------------------------------------------------------


async def extract_platform_signals(events: list[dict]) -> dict:
    """Extract DISC signals from behavioral events.

    Validates each event, detects context modifiers from payloads,
    looks up event-to-signal mappings, applies modifiers, and returns
    a batch result.

    Args:
        events: List of raw event dicts.

    Returns:
        dict with keys:
        - signals: list[dict] - extracted signals with dimension, weight,
          timestamp, evidence
        - signal_count: int
        - dimensions_affected: list[str] - which DISC dimensions have signals
        - success: bool
        - error: str | None
    """
    try:
        all_signals: list[dict[str, Any]] = []
        validation_errors: list[str] = []

        for i, raw_event in enumerate(events):
            # Validate
            validation = validate_event(raw_event)
            if not validation["valid"]:
                validation_errors.append(
                    f"Event {i}: {'; '.join(validation['errors'])}"
                )
                continue

            normalized = validation["normalized_event"]
            if normalized is None:
                continue

            # Extract signals
            signals = _extract_signals_from_event(normalized)
            all_signals.extend(signals)

        # Compute which DISC dimensions are affected
        dimensions_affected = sorted(
            {sig["dimension"] for sig in all_signals}
        )

        return {
            "signals": all_signals,
            "signal_count": len(all_signals),
            "dimensions_affected": dimensions_affected,
            "validation_errors": validation_errors,
            "success": True,
            "error": None,
        }

    except Exception as exc:
        logger.exception("Failed to extract platform signals")
        return {
            "signals": [],
            "signal_count": 0,
            "dimensions_affected": [],
            "validation_errors": [],
            "success": False,
            "error": str(exc),
        }
