"""Tests for behavioral event validation."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services.signal_extractor.validation.event_validator import validate_event


def _make_event(**overrides: object) -> dict:
    """Create a valid event dict with optional overrides."""
    base = {
        "user_id": str(uuid.uuid4()),
        "event_type": "CLICK",
        "payload": {"target": "button_1"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------


class TestRequiredFields:
    """Validate that all required fields are checked."""

    def test_valid_event_passes(self) -> None:
        event = _make_event()
        result = validate_event(event)
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["normalized_event"] is not None

    def test_missing_user_id(self) -> None:
        event = _make_event()
        del event["user_id"]
        result = validate_event(event)
        assert result["valid"] is False
        assert any("user_id" in e for e in result["errors"])

    def test_missing_event_type(self) -> None:
        event = _make_event()
        del event["event_type"]
        result = validate_event(event)
        assert result["valid"] is False
        assert any("event_type" in e for e in result["errors"])

    def test_missing_payload(self) -> None:
        event = _make_event()
        del event["payload"]
        result = validate_event(event)
        assert result["valid"] is False
        assert any("payload" in e for e in result["errors"])

    def test_missing_created_at(self) -> None:
        event = _make_event()
        del event["created_at"]
        result = validate_event(event)
        assert result["valid"] is False
        assert any("created_at" in e for e in result["errors"])

    def test_multiple_missing_fields(self) -> None:
        result = validate_event({})
        assert result["valid"] is False
        assert len(result["errors"]) >= 4  # all required fields missing

    def test_none_input_returns_invalid(self) -> None:
        result = validate_event(None)  # type: ignore[arg-type]
        assert result["valid"] is False
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# user_id validation
# ---------------------------------------------------------------------------


class TestUserIdValidation:
    """Validate user_id format."""

    def test_valid_uuid_string(self) -> None:
        event = _make_event(user_id=str(uuid.uuid4()))
        result = validate_event(event)
        assert result["valid"] is True

    def test_invalid_uuid_string(self) -> None:
        event = _make_event(user_id="not-a-uuid")
        result = validate_event(event)
        assert result["valid"] is False
        assert any("user_id" in e and "UUID" in e for e in result["errors"])

    def test_empty_string_user_id(self) -> None:
        event = _make_event(user_id="")
        result = validate_event(event)
        assert result["valid"] is False

    def test_none_user_id(self) -> None:
        event = _make_event(user_id=None)
        result = validate_event(event)
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# event_type validation
# ---------------------------------------------------------------------------


class TestEventTypeValidation:
    """Validate event_type against supported types."""

    def test_supported_event_type(self) -> None:
        event = _make_event(event_type="TASK_COMPLETED")
        result = validate_event(event)
        assert result["valid"] is True

    def test_unsupported_event_type(self) -> None:
        event = _make_event(event_type="TOTALLY_MADE_UP")
        result = validate_event(event)
        assert result["valid"] is False
        assert any("event_type" in e for e in result["errors"])

    def test_empty_string_event_type(self) -> None:
        event = _make_event(event_type="")
        result = validate_event(event)
        assert result["valid"] is False

    def test_none_event_type(self) -> None:
        event = _make_event(event_type=None)
        result = validate_event(event)
        assert result["valid"] is False

    def test_all_known_event_types_pass(self) -> None:
        """Every event type from the mappings should be accepted."""
        from app.services.signal_extractor.mappings.event_mappings import (
            get_all_event_types,
        )

        for et in get_all_event_types():
            event = _make_event(event_type=et)
            result = validate_event(event)
            assert result["valid"] is True, f"Event type {et} should be valid"


# ---------------------------------------------------------------------------
# payload validation
# ---------------------------------------------------------------------------


class TestPayloadValidation:
    """Validate payload structure."""

    def test_dict_payload(self) -> None:
        event = _make_event(payload={"key": "value"})
        result = validate_event(event)
        assert result["valid"] is True

    def test_empty_dict_payload(self) -> None:
        event = _make_event(payload={})
        result = validate_event(event)
        assert result["valid"] is True

    def test_string_payload_invalid(self) -> None:
        event = _make_event(payload="not a dict")
        result = validate_event(event)
        assert result["valid"] is False
        assert any("payload" in e for e in result["errors"])

    def test_list_payload_invalid(self) -> None:
        event = _make_event(payload=[1, 2, 3])
        result = validate_event(event)
        assert result["valid"] is False
        assert any("payload" in e for e in result["errors"])

    def test_none_payload(self) -> None:
        event = _make_event(payload=None)
        result = validate_event(event)
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# created_at timestamp validation
# ---------------------------------------------------------------------------


class TestCreatedAtValidation:
    """Validate created_at timestamps."""

    def test_valid_iso_timestamp(self) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        event = _make_event(created_at=ts)
        result = validate_event(event)
        assert result["valid"] is True

    def test_valid_datetime_object(self) -> None:
        event = _make_event(created_at=datetime.now(timezone.utc))
        result = validate_event(event)
        assert result["valid"] is True

    def test_future_timestamp_rejected(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(hours=25)
        event = _make_event(created_at=future.isoformat())
        result = validate_event(event)
        assert result["valid"] is False
        assert any("future" in e.lower() for e in result["errors"])

    def test_slightly_future_timestamp_warning(self) -> None:
        """A timestamp within 24h in the future should produce a warning, not error."""
        near_future = datetime.now(timezone.utc) + timedelta(hours=1)
        event = _make_event(created_at=near_future.isoformat())
        result = validate_event(event)
        assert result["valid"] is True
        assert any("future" in w.lower() for w in result["warnings"])

    def test_very_old_timestamp_rejected(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(days=400)
        event = _make_event(created_at=old.isoformat())
        result = validate_event(event)
        assert result["valid"] is False
        assert any("old" in e.lower() for e in result["errors"])

    def test_timestamp_just_within_365_days(self) -> None:
        """A timestamp 364 days old should still be valid."""
        just_old = datetime.now(timezone.utc) - timedelta(days=364)
        event = _make_event(created_at=just_old.isoformat())
        result = validate_event(event)
        assert result["valid"] is True

    def test_unparseable_timestamp(self) -> None:
        event = _make_event(created_at="not-a-date")
        result = validate_event(event)
        assert result["valid"] is False
        assert any("created_at" in e for e in result["errors"])

    def test_none_created_at(self) -> None:
        event = _make_event(created_at=None)
        result = validate_event(event)
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# Optional field: session_id
# ---------------------------------------------------------------------------


class TestSessionIdValidation:
    """Validate optional session_id field."""

    def test_valid_session_id(self) -> None:
        event = _make_event(session_id=str(uuid.uuid4()))
        result = validate_event(event)
        assert result["valid"] is True

    def test_invalid_session_id(self) -> None:
        event = _make_event(session_id="not-a-uuid")
        result = validate_event(event)
        assert result["valid"] is False
        assert any("session_id" in e for e in result["errors"])

    def test_absent_session_id_is_ok(self) -> None:
        event = _make_event()
        assert "session_id" not in event
        result = validate_event(event)
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# Optional field: latency_ms
# ---------------------------------------------------------------------------


class TestLatencyMsValidation:
    """Validate optional latency_ms field."""

    def test_valid_latency(self) -> None:
        event = _make_event(latency_ms=150)
        result = validate_event(event)
        assert result["valid"] is True

    def test_zero_latency(self) -> None:
        event = _make_event(latency_ms=0)
        result = validate_event(event)
        assert result["valid"] is True

    def test_negative_latency(self) -> None:
        event = _make_event(latency_ms=-10)
        result = validate_event(event)
        assert result["valid"] is False
        assert any("latency_ms" in e for e in result["errors"])

    def test_non_integer_latency(self) -> None:
        event = _make_event(latency_ms="fast")
        result = validate_event(event)
        assert result["valid"] is False
        assert any("latency_ms" in e for e in result["errors"])

    def test_absent_latency_is_ok(self) -> None:
        event = _make_event()
        assert "latency_ms" not in event
        result = validate_event(event)
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# Optional field: client_type
# ---------------------------------------------------------------------------


class TestClientTypeValidation:
    """Validate optional client_type field."""

    def test_valid_client_types(self) -> None:
        for ct in ("web", "mobile", "api", "desktop"):
            event = _make_event(client_type=ct)
            result = validate_event(event)
            assert result["valid"] is True, f"client_type={ct} should be valid"

    def test_invalid_client_type(self) -> None:
        event = _make_event(client_type="toaster")
        result = validate_event(event)
        assert result["valid"] is False
        assert any("client_type" in e for e in result["errors"])

    def test_absent_client_type_is_ok(self) -> None:
        event = _make_event()
        assert "client_type" not in event
        result = validate_event(event)
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# Normalized event output
# ---------------------------------------------------------------------------


class TestNormalizedEvent:
    """Check the normalized event in the result."""

    def test_normalized_event_present_on_success(self) -> None:
        event = _make_event()
        result = validate_event(event)
        assert result["normalized_event"] is not None
        assert result["normalized_event"]["user_id"] == event["user_id"]
        assert result["normalized_event"]["event_type"] == event["event_type"]

    def test_normalized_event_none_on_failure(self) -> None:
        result = validate_event({})
        assert result["normalized_event"] is None

    def test_normalized_event_has_parsed_datetime(self) -> None:
        ts = datetime.now(timezone.utc)
        event = _make_event(created_at=ts.isoformat())
        result = validate_event(event)
        norm = result["normalized_event"]
        assert isinstance(norm["created_at"], datetime)


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------


class TestReturnStructure:
    """Ensure return dict always has required keys."""

    def test_valid_event_return_keys(self) -> None:
        result = validate_event(_make_event())
        assert "valid" in result
        assert "errors" in result
        assert "warnings" in result
        assert "normalized_event" in result

    def test_invalid_event_return_keys(self) -> None:
        result = validate_event({})
        assert "valid" in result
        assert "errors" in result
        assert "warnings" in result
        assert "normalized_event" in result

    def test_errors_is_list(self) -> None:
        result = validate_event({})
        assert isinstance(result["errors"], list)

    def test_warnings_is_list(self) -> None:
        result = validate_event(_make_event())
        assert isinstance(result["warnings"], list)
