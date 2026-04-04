"""Tests for the Signal Extractor Worker service."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.services.signal_extractor.worker import process_behavioral_events

# ---- helpers -----------------------------------------------------------------

NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())


def _event(
    event_type: str,
    payload: dict | None = None,
    *,
    user_id: str = USER_A,
    created_at: datetime | None = None,
    **extra: object,
) -> dict[str, Any]:
    """Build a valid raw event dict."""
    return {
        "user_id": user_id,
        "event_type": event_type,
        "payload": payload or {},
        "created_at": (created_at or NOW).isoformat(),
        **extra,
    }


# ---------------------------------------------------------------------------
# Basic pipeline tests
# ---------------------------------------------------------------------------


class TestBasicPipeline:
    """End-to-end tests for the orchestration pipeline."""

    @pytest.mark.asyncio
    async def test_single_valid_event(self) -> None:
        result = await process_behavioral_events([_event("CLICK")])
        assert result["success"] is True
        assert result["error"] is None
        assert result["signal_count"] > 0
        assert result["valid_events"] == 1
        assert result["invalid_events"] == 0
        assert result["validation_errors"] == []

    @pytest.mark.asyncio
    async def test_empty_event_list(self) -> None:
        result = await process_behavioral_events([])
        assert result["success"] is True
        assert result["signal_count"] == 0
        assert result["valid_events"] == 0
        assert result["invalid_events"] == 0
        assert result["overall_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_multiple_valid_events(self) -> None:
        events = [
            _event("CLICK"),
            _event("MESSAGE_SENT"),
            _event("TASK_STARTED"),
        ]
        result = await process_behavioral_events(events)
        assert result["success"] is True
        assert result["valid_events"] == 3
        assert result["signal_count"] >= 3  # at least one signal per event

    @pytest.mark.asyncio
    async def test_mixed_valid_and_invalid_events(self) -> None:
        events = [
            _event("CLICK"),
            {"bad": "event"},
            _event("MESSAGE_SENT"),
        ]
        result = await process_behavioral_events(events)
        assert result["success"] is True
        assert result["valid_events"] == 2
        assert result["invalid_events"] == 1
        assert len(result["validation_errors"]) == 1

    @pytest.mark.asyncio
    async def test_all_invalid_events(self) -> None:
        events = [
            {"bad": "event"},
            {"also": "bad"},
        ]
        result = await process_behavioral_events(events)
        assert result["success"] is True
        assert result["signal_count"] == 0
        assert result["valid_events"] == 0
        assert result["invalid_events"] == 2
        assert len(result["validation_errors"]) == 2


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------


class TestResponseStructure:
    """Verify the response dict has all required keys."""

    @pytest.mark.asyncio
    async def test_all_keys_present(self) -> None:
        result = await process_behavioral_events([_event("CLICK")])
        expected_keys = {
            "signals",
            "confidence",
            "overall_confidence",
            "signal_count",
            "valid_events",
            "invalid_events",
            "validation_errors",
            "success",
            "error",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_confidence_has_disc_dimensions(self) -> None:
        result = await process_behavioral_events([_event("CLICK")])
        assert set(result["confidence"].keys()) == {"D", "I", "S", "C"}

    @pytest.mark.asyncio
    async def test_confidence_values_in_range(self) -> None:
        events = [
            _event("CLICK"),
            _event("MESSAGE_SENT"),
            _event("TASK_COMPLETED"),
            _event("FORM_SUBMIT"),
        ]
        result = await process_behavioral_events(events)
        for dim, score in result["confidence"].items():
            assert 0.0 <= score <= 1.0, f"{dim} score {score} out of range"
        assert 0.0 <= result["overall_confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_error_response_structure(self) -> None:
        """Even on empty input, the response should have the full structure."""
        result = await process_behavioral_events([])
        assert result["success"] is True
        assert result["error"] is None
        assert isinstance(result["signals"], list)
        assert isinstance(result["validation_errors"], list)


# ---------------------------------------------------------------------------
# User filtering
# ---------------------------------------------------------------------------


class TestUserFiltering:
    """Tests for the user_id filtering parameter."""

    @pytest.mark.asyncio
    async def test_filter_by_user_id(self) -> None:
        events = [
            _event("CLICK", user_id=USER_A),
            _event("MESSAGE_SENT", user_id=USER_B),
            _event("TASK_STARTED", user_id=USER_A),
        ]
        result = await process_behavioral_events(events, user_id=USER_A)
        assert result["valid_events"] == 2
        # Only USER_A events should be processed
        for sig in result["signals"]:
            assert sig["evidence"]["user_id"] == USER_A

    @pytest.mark.asyncio
    async def test_filter_with_no_matching_user(self) -> None:
        events = [
            _event("CLICK", user_id=USER_A),
        ]
        result = await process_behavioral_events(
            events, user_id=str(uuid.uuid4())
        )
        assert result["valid_events"] == 0
        assert result["signal_count"] == 0

    @pytest.mark.asyncio
    async def test_no_filter_processes_all_users(self) -> None:
        events = [
            _event("CLICK", user_id=USER_A),
            _event("CLICK", user_id=USER_B),
        ]
        result = await process_behavioral_events(events)
        assert result["valid_events"] == 2


# ---------------------------------------------------------------------------
# Window days parameter
# ---------------------------------------------------------------------------


class TestWindowDays:
    """Tests for the window_days confidence parameter."""

    @pytest.mark.asyncio
    async def test_default_window_30_days(self) -> None:
        events = [_event("CLICK")]
        result = await process_behavioral_events(events)
        # Should succeed with default window
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_custom_window_days(self) -> None:
        events = [_event("CLICK")]
        result = await process_behavioral_events(events, window_days=7)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_narrow_window_may_reduce_confidence(self) -> None:
        """Events near the edge of a narrow window get more decay."""
        old_time = NOW - timedelta(days=25)
        events = [_event("CLICK", created_at=old_time)]

        result_wide = await process_behavioral_events(events, window_days=30)
        result_narrow = await process_behavioral_events(events, window_days=7)

        # The 25-day-old event falls outside a 7-day window, so the narrow
        # result should have no signals contributing to confidence.
        assert result_narrow["overall_confidence"] <= result_wide["overall_confidence"]


# ---------------------------------------------------------------------------
# Signal extraction integration
# ---------------------------------------------------------------------------


class TestSignalExtraction:
    """Verify signal extraction is correctly wired."""

    @pytest.mark.asyncio
    async def test_signals_have_expected_fields(self) -> None:
        result = await process_behavioral_events([_event("CLICK")])
        for sig in result["signals"]:
            assert "id" in sig
            assert "dimension" in sig
            assert "weight" in sig
            assert "timestamp" in sig
            assert "event_type" in sig
            assert "evidence" in sig

    @pytest.mark.asyncio
    async def test_context_modifiers_applied(self) -> None:
        events = [_event("MESSAGE_RESPONDED", {"latency_ms": 100})]
        result = await process_behavioral_events(events)
        responded = [
            s for s in result["signals"]
            if s["event_type"] == "MESSAGE_RESPONDED"
        ]
        assert any(
            "fast_response" in s["evidence"]["modifiers_applied"]
            for s in responded
        )

    @pytest.mark.asyncio
    async def test_signal_count_matches_signals_list(self) -> None:
        events = [_event("CLICK"), _event("MESSAGE_SENT")]
        result = await process_behavioral_events(events)
        assert result["signal_count"] == len(result["signals"])


# ---------------------------------------------------------------------------
# Confidence integration
# ---------------------------------------------------------------------------


class TestConfidenceIntegration:
    """Verify confidence calculation is correctly wired."""

    @pytest.mark.asyncio
    async def test_confidence_computed_from_signals(self) -> None:
        # D-heavy events should yield D confidence > 0
        events = [
            _event("CLICK"),
            _event("TASK_STARTED"),
            _event("TASK_COMPLETED"),
        ]
        result = await process_behavioral_events(events)
        assert result["confidence"]["D"] > 0.0

    @pytest.mark.asyncio
    async def test_no_signals_yields_zero_confidence(self) -> None:
        result = await process_behavioral_events([])
        assert result["overall_confidence"] == 0.0
        for score in result["confidence"].values():
            assert score == 0.0

    @pytest.mark.asyncio
    async def test_more_signals_generally_higher_confidence(self) -> None:
        few = [_event("CLICK")]
        many = [_event("CLICK") for _ in range(10)]

        result_few = await process_behavioral_events(few)
        result_many = await process_behavioral_events(many)

        assert result_many["overall_confidence"] >= result_few["overall_confidence"]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Worker should never raise; errors are captured in the response."""

    @pytest.mark.asyncio
    async def test_non_dict_event_is_invalid(self) -> None:
        result = await process_behavioral_events(["not_a_dict"])  # type: ignore[list-item]
        assert result["success"] is True
        assert result["invalid_events"] == 1

    @pytest.mark.asyncio
    async def test_none_in_event_list(self) -> None:
        result = await process_behavioral_events([None])  # type: ignore[list-item]
        assert result["success"] is True
        assert result["invalid_events"] == 1

    @pytest.mark.asyncio
    async def test_validation_error_messages_are_descriptive(self) -> None:
        events = [{"user_id": "not-a-uuid", "event_type": "CLICK", "payload": {}, "created_at": NOW.isoformat()}]
        result = await process_behavioral_events(events)
        assert result["invalid_events"] == 1
        assert any("user_id" in err for err in result["validation_errors"])


# ---------------------------------------------------------------------------
# Large batch
# ---------------------------------------------------------------------------


class TestLargeBatch:
    """Verify the worker handles large batches."""

    @pytest.mark.asyncio
    async def test_large_batch_succeeds(self) -> None:
        events = [_event("CLICK") for _ in range(200)]
        result = await process_behavioral_events(events)
        assert result["success"] is True
        assert result["valid_events"] == 200
        assert result["signal_count"] == 400  # CLICK -> 2 signals each
