"""Behavioral event validation.

Validates incoming behavioral events before they are processed by the
signal extractor pipeline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.signal_extractor.mappings.event_mappings import get_all_event_types

# ---- constants ---------------------------------------------------------------

_SUPPORTED_EVENT_TYPES: set[str] | None = None  # lazy-loaded

ALLOWED_CLIENT_TYPES = frozenset({"web", "mobile", "api", "desktop"})

MAX_FUTURE_HOURS = 24
MAX_AGE_DAYS = 365

REQUIRED_FIELDS = ("user_id", "event_type", "payload", "created_at")


# ---- helpers -----------------------------------------------------------------


def _supported_event_types() -> set[str]:
    """Return the set of supported event types (lazy-loaded)."""
    global _SUPPORTED_EVENT_TYPES
    if _SUPPORTED_EVENT_TYPES is None:
        _SUPPORTED_EVENT_TYPES = set(get_all_event_types())
    return _SUPPORTED_EVENT_TYPES


def _is_valid_uuid(value: str) -> bool:
    """Return True if *value* is a valid UUID string."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def _parse_datetime(value: Any) -> datetime | None:
    """Parse *value* into a timezone-aware datetime, or return None."""
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


# ---- public API --------------------------------------------------------------


def validate_event(event: dict) -> dict:  # type: ignore[type-arg]
    """Validate a behavioral event.

    Args:
        event: Raw event dict.

    Returns:
        dict with keys:
        - valid: bool
        - errors: list[str]  – validation error messages
        - warnings: list[str] – non-fatal warnings
        - normalized_event: dict | None – cleaned/normalized event if valid
    """
    errors: list[str] = []
    warnings: list[str] = []

    # -- guard against non-dict input ------------------------------------------
    if not isinstance(event, dict):
        return {
            "valid": False,
            "errors": ["Event must be a dict"],
            "warnings": [],
            "normalized_event": None,
        }

    # -- required field presence -----------------------------------------------
    for field in REQUIRED_FIELDS:
        if field not in event or event[field] is None:
            errors.append(f"Missing required field: {field}")

    # Early-exit if required fields are missing; further validation would be
    # meaningless.
    if errors:
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "normalized_event": None,
        }

    # -- user_id ---------------------------------------------------------------
    user_id = event["user_id"]
    if not isinstance(user_id, str) or not _is_valid_uuid(user_id):
        errors.append("user_id must be a valid UUID string")

    # -- event_type ------------------------------------------------------------
    event_type = event["event_type"]
    if not isinstance(event_type, str) or not event_type:
        errors.append("event_type must be a non-empty string")
    elif event_type not in _supported_event_types():
        errors.append(
            f"Unsupported event_type: {event_type!r}. "
            f"Must be one of the supported event types."
        )

    # -- payload ---------------------------------------------------------------
    payload = event["payload"]
    if not isinstance(payload, dict):
        errors.append("payload must be a dict")

    # -- created_at ------------------------------------------------------------
    parsed_dt = _parse_datetime(event["created_at"])
    if parsed_dt is None:
        errors.append("created_at must be a valid ISO-8601 datetime string or datetime object")
    else:
        now = datetime.now(timezone.utc)
        if parsed_dt > now + timedelta(hours=MAX_FUTURE_HOURS):
            errors.append(
                f"created_at is too far in the future "
                f"(more than {MAX_FUTURE_HOURS}h ahead)"
            )
        elif parsed_dt > now:
            warnings.append(
                "created_at is slightly in the future; clock skew?"
            )
        if parsed_dt < now - timedelta(days=MAX_AGE_DAYS):
            errors.append(
                f"created_at is too old (older than {MAX_AGE_DAYS} days)"
            )

    # -- optional: session_id --------------------------------------------------
    if "session_id" in event:
        session_id = event["session_id"]
        if not isinstance(session_id, str) or not _is_valid_uuid(session_id):
            errors.append("session_id must be a valid UUID string")

    # -- optional: latency_ms --------------------------------------------------
    if "latency_ms" in event:
        latency = event["latency_ms"]
        if not isinstance(latency, int) or isinstance(latency, bool):
            errors.append("latency_ms must be a non-negative integer")
        elif latency < 0:
            errors.append("latency_ms must be a non-negative integer")

    # -- optional: client_type -------------------------------------------------
    if "client_type" in event:
        ct = event["client_type"]
        if ct not in ALLOWED_CLIENT_TYPES:
            errors.append(
                f"client_type must be one of {sorted(ALLOWED_CLIENT_TYPES)}, "
                f"got {ct!r}"
            )

    # -- build result ----------------------------------------------------------
    if errors:
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "normalized_event": None,
        }

    # Produce the normalized event with a parsed datetime.
    normalized: dict[str, Any] = {
        "user_id": event["user_id"],
        "event_type": event["event_type"],
        "payload": event["payload"],
        "created_at": parsed_dt,
    }
    # Carry over optional fields that were present
    for opt_field in ("session_id", "latency_ms", "client_type"):
        if opt_field in event:
            normalized[opt_field] = event[opt_field]

    return {
        "valid": True,
        "errors": [],
        "warnings": warnings,
        "normalized_event": normalized,
    }
