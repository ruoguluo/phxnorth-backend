"""Signal Extractor Worker service.

Orchestrates the full behavioral-event processing pipeline:
validation → signal extraction → confidence calculation.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.signal_extractor.confidence.calculator import (
    calculate_signal_confidence,
)
from app.services.signal_extractor.extractors.platform_signals import (
    extract_platform_signals,
)
from app.services.signal_extractor.validation.event_validator import validate_event

logger = logging.getLogger(__name__)


# ---- helpers -----------------------------------------------------------------


def _filter_events_by_user(
    events: list[dict[str, Any]],
    user_id: str,
) -> list[dict[str, Any]]:
    """Return only events belonging to *user_id*."""
    return [e for e in events if e.get("user_id") == user_id]


# ---- public API --------------------------------------------------------------


async def process_behavioral_events(
    events: list[dict],
    user_id: str | None = None,
    window_days: int = 30,
) -> dict:
    """Process behavioral events and extract DISC signals.

    Orchestrates the full pipeline:

    1. **Filter** – optionally restrict to a single user.
    2. **Validate** – each event is passed through the event validator;
       invalid events are counted and their errors collected.
    3. **Extract** – valid events are fed to the platform signal extractor,
       which maps events to weighted DISC signals with context modifiers.
    4. **Confidence** – the extracted signals are scored for per-dimension
       and overall confidence using temporal decay.

    Args:
        events: List of raw behavioral event dicts.
        user_id: Optional user ID for filtering.  When provided only events
            whose ``user_id`` field matches are processed.
        window_days: Time window (in days) passed to the confidence
            calculator.  Signals older than this are excluded from the
            confidence computation.

    Returns:
        dict with keys:

        * **signals** – ``list[dict]`` all extracted signals.
        * **confidence** – ``dict`` per-dimension confidence scores
          (``D``, ``I``, ``S``, ``C``).
        * **overall_confidence** – ``float`` combined confidence.
        * **signal_count** – ``int`` number of extracted signals.
        * **valid_events** – ``int`` events that passed validation.
        * **invalid_events** – ``int`` events that failed validation.
        * **validation_errors** – ``list[str]`` human-readable error
          messages for invalid events.
        * **success** – ``bool`` ``True`` when the pipeline completed
          without an unhandled exception.
        * **error** – ``str | None`` error message if *success* is
          ``False``.
    """
    try:
        # -- 1. Optional user filtering ----------------------------------------
        working_events = events
        if user_id is not None:
            working_events = _filter_events_by_user(events, user_id)

        # -- 2. Validate -------------------------------------------------------
        valid_raw_events: list[dict[str, Any]] = []
        validation_errors: list[str] = []
        valid_count = 0
        invalid_count = 0

        for idx, raw_event in enumerate(working_events):
            result = validate_event(raw_event)
            if result["valid"]:
                valid_count += 1
                valid_raw_events.append(raw_event)
            else:
                invalid_count += 1
                validation_errors.append(
                    f"Event {idx}: {'; '.join(result['errors'])}"
                )

        # -- 3. Extract signals ------------------------------------------------
        # Pass the pre-validated raw events to the extractor.
        # extract_platform_signals will re-validate internally (cheap for
        # already-valid events) and apply context-modifier detection.
        extraction = await extract_platform_signals(valid_raw_events)

        if not extraction["success"]:
            return _error_result(
                extraction.get("error", "Signal extraction failed"),
                validation_errors=validation_errors,
                valid_events=valid_count,
                invalid_events=invalid_count,
            )

        signals = extraction["signals"]

        # -- 4. Confidence calculation -----------------------------------------
        confidence_result = calculate_signal_confidence(
            signals,
            window_days=window_days,
        )

        return {
            "signals": signals,
            "confidence": confidence_result["dimension_scores"],
            "overall_confidence": confidence_result["overall_confidence"],
            "signal_count": len(signals),
            "valid_events": valid_count,
            "invalid_events": invalid_count,
            "validation_errors": validation_errors,
            "success": True,
            "error": None,
        }

    except Exception as exc:
        logger.exception("Signal extractor worker failed")
        return _error_result(str(exc))


def _error_result(
    error: str,
    *,
    validation_errors: list[str] | None = None,
    valid_events: int = 0,
    invalid_events: int = 0,
) -> dict[str, Any]:
    """Build a standardised error response."""
    return {
        "signals": [],
        "confidence": {"D": 0.0, "I": 0.0, "S": 0.0, "C": 0.0},
        "overall_confidence": 0.0,
        "signal_count": 0,
        "valid_events": valid_events,
        "invalid_events": invalid_events,
        "validation_errors": validation_errors or [],
        "success": False,
        "error": error,
    }
