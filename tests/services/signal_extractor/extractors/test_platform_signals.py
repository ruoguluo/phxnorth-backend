"""Tests for platform signal extraction."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services.signal_extractor.extractors.platform_signals import (
    _detect_context_modifiers,
    _extract_signals_from_event,
    extract_platform_signals,
)

# ---- helpers -----------------------------------------------------------------

NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
USER_ID = str(uuid.uuid4())


def _event(
    event_type: str,
    payload: dict | None = None,
    *,
    user_id: str = USER_ID,
    created_at: datetime | None = None,
    **extra: object,
) -> dict:
    """Build a valid raw event dict."""
    return {
        "user_id": user_id,
        "event_type": event_type,
        "payload": payload or {},
        "created_at": (created_at or NOW).isoformat(),
        **extra,
    }


# ---------------------------------------------------------------------------
# Context modifier detection
# ---------------------------------------------------------------------------


class TestContextModifierDetection:
    """Unit tests for _detect_context_modifiers."""

    # -- MESSAGE_RESPONDED --

    def test_fast_response_detected(self) -> None:
        event = _event("MESSAGE_RESPONDED", {"latency_ms": 200})
        mods = _detect_context_modifiers("MESSAGE_RESPONDED", event)
        assert "fast_response" in mods

    def test_slow_response_detected(self) -> None:
        event = _event("MESSAGE_RESPONDED", {"latency_ms": 4_000_000})
        mods = _detect_context_modifiers("MESSAGE_RESPONDED", event)
        assert "slow_response" in mods

    def test_normal_response_no_modifier(self) -> None:
        event = _event("MESSAGE_RESPONDED", {"latency_ms": 60_000})
        mods = _detect_context_modifiers("MESSAGE_RESPONDED", event)
        assert mods == []

    def test_message_responded_latency_at_boundary_fast(self) -> None:
        """Exactly 300ms should NOT be fast (< 300 required)."""
        event = _event("MESSAGE_RESPONDED", {"latency_ms": 300})
        mods = _detect_context_modifiers("MESSAGE_RESPONDED", event)
        assert "fast_response" not in mods

    def test_message_responded_latency_at_boundary_slow(self) -> None:
        """Exactly 3600000ms should NOT be slow (> 3600000 required)."""
        event = _event("MESSAGE_RESPONDED", {"latency_ms": 3_600_000})
        mods = _detect_context_modifiers("MESSAGE_RESPONDED", event)
        assert "slow_response" not in mods

    # -- TASK_COMPLETED --

    def test_early_completion_detected(self) -> None:
        deadline = NOW + timedelta(hours=2)
        event = _event("TASK_COMPLETED", {
            "deadline": deadline.isoformat(),
            "completed_at": NOW.isoformat(),
        })
        mods = _detect_context_modifiers("TASK_COMPLETED", event)
        assert "early_completion" in mods

    def test_late_completion_detected(self) -> None:
        deadline = NOW - timedelta(hours=2)
        event = _event("TASK_COMPLETED", {
            "deadline": deadline.isoformat(),
            "completed_at": NOW.isoformat(),
        })
        mods = _detect_context_modifiers("TASK_COMPLETED", event)
        assert "late" in mods

    def test_on_time_completion_detected(self) -> None:
        deadline = NOW + timedelta(minutes=30)
        event = _event("TASK_COMPLETED", {
            "deadline": deadline.isoformat(),
            "completed_at": NOW.isoformat(),
        })
        mods = _detect_context_modifiers("TASK_COMPLETED", event)
        assert "on_time" in mods

    def test_task_no_deadline_no_modifier(self) -> None:
        event = _event("TASK_COMPLETED", {})
        mods = _detect_context_modifiers("TASK_COMPLETED", event)
        assert mods == []

    # -- ASSESSMENT_QUESTION_ANSWER --

    def test_quick_answer_detected(self) -> None:
        event = _event("ASSESSMENT_QUESTION_ANSWER", {"duration_seconds": 5})
        mods = _detect_context_modifiers("ASSESSMENT_QUESTION_ANSWER", event)
        assert "quick_answer" in mods

    def test_thoughtful_answer_detected(self) -> None:
        event = _event("ASSESSMENT_QUESTION_ANSWER", {"duration_seconds": 90})
        mods = _detect_context_modifiers("ASSESSMENT_QUESTION_ANSWER", event)
        assert "thoughtful_answer" in mods

    def test_normal_answer_no_modifier(self) -> None:
        event = _event("ASSESSMENT_QUESTION_ANSWER", {"duration_seconds": 30})
        mods = _detect_context_modifiers("ASSESSMENT_QUESTION_ANSWER", event)
        assert mods == []

    # -- SESSION_END --

    def test_long_session_detected(self) -> None:
        event = _event("SESSION_END", {"duration_minutes": 45})
        mods = _detect_context_modifiers("SESSION_END", event)
        assert "long_session" in mods

    def test_short_session_detected(self) -> None:
        event = _event("SESSION_END", {"duration_minutes": 3})
        mods = _detect_context_modifiers("SESSION_END", event)
        assert "short_session" in mods

    def test_normal_session_no_modifier(self) -> None:
        event = _event("SESSION_END", {"duration_minutes": 15})
        mods = _detect_context_modifiers("SESSION_END", event)
        assert mods == []

    # -- SCROLL --

    def test_deep_scroll_detected(self) -> None:
        event = _event("SCROLL", {"scroll_depth_percent": 95})
        mods = _detect_context_modifiers("SCROLL", event)
        assert "deep_scroll" in mods

    def test_shallow_scroll_detected(self) -> None:
        event = _event("SCROLL", {"scroll_depth_percent": 10})
        mods = _detect_context_modifiers("SCROLL", event)
        assert "shallow_scroll" in mods

    def test_mid_scroll_no_modifier(self) -> None:
        event = _event("SCROLL", {"scroll_depth_percent": 50})
        mods = _detect_context_modifiers("SCROLL", event)
        assert mods == []

    # -- QUESTION_POSTED --

    def test_detailed_question_detected(self) -> None:
        event = _event("QUESTION_POSTED", {"question_text": "x" * 150})
        mods = _detect_context_modifiers("QUESTION_POSTED", event)
        assert "detailed_question" in mods

    def test_brief_question_detected(self) -> None:
        event = _event("QUESTION_POSTED", {"question_text": "Why?"})
        mods = _detect_context_modifiers("QUESTION_POSTED", event)
        assert "brief_question" in mods

    def test_normal_question_no_modifier(self) -> None:
        event = _event("QUESTION_POSTED", {
            "question_text": "How does the assessment scoring work for DISC?"
        })
        mods = _detect_context_modifiers("QUESTION_POSTED", event)
        assert mods == []

    # -- Events without detectors --

    def test_event_with_no_detectors_returns_empty(self) -> None:
        event = _event("CLICK", {})
        mods = _detect_context_modifiers("CLICK", event)
        assert mods == []


# ---------------------------------------------------------------------------
# Single event signal extraction
# ---------------------------------------------------------------------------


class TestSingleEventExtraction:
    """Tests for _extract_signals_from_event."""

    def test_basic_signal_extraction(self) -> None:
        """MESSAGE_SENT should produce D and I signals."""
        event = {
            "user_id": USER_ID,
            "event_type": "MESSAGE_SENT",
            "payload": {},
            "created_at": NOW,
        }
        signals = _extract_signals_from_event(event)
        assert len(signals) == 2
        dims = {s["dimension"] for s in signals}
        assert dims == {"I", "D"}

    def test_signals_have_required_fields(self) -> None:
        event = {
            "user_id": USER_ID,
            "event_type": "CLICK",
            "payload": {},
            "created_at": NOW,
        }
        signals = _extract_signals_from_event(event)
        for sig in signals:
            assert "id" in sig
            assert "dimension" in sig
            assert "weight" in sig
            assert "timestamp" in sig
            assert "event_type" in sig
            assert "evidence" in sig

    def test_modifier_adjusts_weight(self) -> None:
        """Fast response should boost D and I weights."""
        base_event = {
            "user_id": USER_ID,
            "event_type": "MESSAGE_RESPONDED",
            "payload": {"latency_ms": 60_000},
            "created_at": NOW,
        }
        fast_event = {
            "user_id": USER_ID,
            "event_type": "MESSAGE_RESPONDED",
            "payload": {"latency_ms": 100},
            "created_at": NOW,
        }
        base_signals = _extract_signals_from_event(base_event)
        fast_signals = _extract_signals_from_event(fast_event)

        base_d = next(s for s in base_signals if s["dimension"] == "D")
        fast_d = next(s for s in fast_signals if s["dimension"] == "D")
        # fast_response adds 0.2 to D
        assert fast_d["weight"] > base_d["weight"]

    def test_unknown_event_type_returns_empty(self) -> None:
        event = {
            "user_id": USER_ID,
            "event_type": "UNKNOWN_EVENT",
            "payload": {},
            "created_at": NOW,
        }
        signals = _extract_signals_from_event(event)
        assert signals == []

    def test_evidence_contains_event_type(self) -> None:
        event = {
            "user_id": USER_ID,
            "event_type": "TASK_STARTED",
            "payload": {},
            "created_at": NOW,
        }
        signals = _extract_signals_from_event(event)
        for sig in signals:
            assert sig["evidence"]["event_type"] == "TASK_STARTED"

    def test_evidence_contains_modifier_info(self) -> None:
        event = {
            "user_id": USER_ID,
            "event_type": "SCROLL",
            "payload": {"scroll_depth_percent": 95},
            "created_at": NOW,
        }
        signals = _extract_signals_from_event(event)
        for sig in signals:
            assert "deep_scroll" in sig["evidence"]["modifiers_applied"]

    def test_timestamp_from_created_at(self) -> None:
        event = {
            "user_id": USER_ID,
            "event_type": "CLICK",
            "payload": {},
            "created_at": NOW,
        }
        signals = _extract_signals_from_event(event)
        for sig in signals:
            assert sig["timestamp"] == NOW.isoformat()


# ---------------------------------------------------------------------------
# Batch extraction (extract_platform_signals)
# ---------------------------------------------------------------------------


class TestBatchExtraction:
    """Tests for the main extract_platform_signals function."""

    @pytest.mark.asyncio
    async def test_single_valid_event(self) -> None:
        events = [_event("CLICK")]
        result = await extract_platform_signals(events)
        assert result["success"] is True
        assert result["error"] is None
        assert result["signal_count"] == 2  # CLICK -> D + I
        assert "D" in result["dimensions_affected"]
        assert "I" in result["dimensions_affected"]

    @pytest.mark.asyncio
    async def test_empty_event_list(self) -> None:
        result = await extract_platform_signals([])
        assert result["success"] is True
        assert result["signal_count"] == 0
        assert result["dimensions_affected"] == []
        assert result["signals"] == []

    @pytest.mark.asyncio
    async def test_invalid_event_skipped(self) -> None:
        events = [
            {"not_a_valid": "event"},
            _event("CLICK"),
        ]
        result = await extract_platform_signals(events)
        assert result["success"] is True
        assert result["signal_count"] == 2  # only CLICK signals
        assert len(result["validation_errors"]) == 1

    @pytest.mark.asyncio
    async def test_multiple_valid_events(self) -> None:
        events = [
            _event("CLICK"),
            _event("MESSAGE_SENT"),
            _event("TASK_STARTED"),
        ]
        result = await extract_platform_signals(events)
        assert result["success"] is True
        # CLICK(2) + MESSAGE_SENT(2) + TASK_STARTED(2) = 6
        assert result["signal_count"] == 6

    @pytest.mark.asyncio
    async def test_dimensions_affected_accurate(self) -> None:
        events = [_event("FORM_START")]  # C only
        result = await extract_platform_signals(events)
        assert result["dimensions_affected"] == ["C"]

    @pytest.mark.asyncio
    async def test_batch_with_modifiers(self) -> None:
        events = [
            _event("MESSAGE_RESPONDED", {"latency_ms": 100}),
            _event("SCROLL", {"scroll_depth_percent": 95}),
        ]
        result = await extract_platform_signals(events)
        assert result["success"] is True

        # Check that modifiers are recorded in evidence
        responded_signals = [
            s for s in result["signals"] if s["event_type"] == "MESSAGE_RESPONDED"
        ]
        for sig in responded_signals:
            assert "fast_response" in sig["evidence"]["modifiers_applied"]

    @pytest.mark.asyncio
    async def test_all_invalid_events(self) -> None:
        events = [
            {"bad": "event"},
            {"also": "bad"},
        ]
        result = await extract_platform_signals(events)
        assert result["success"] is True
        assert result["signal_count"] == 0
        assert len(result["validation_errors"]) == 2

    @pytest.mark.asyncio
    async def test_signal_ids_are_unique(self) -> None:
        events = [_event("CLICK"), _event("CLICK")]
        result = await extract_platform_signals(events)
        ids = [s["id"] for s in result["signals"]]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_signals_have_correct_event_type(self) -> None:
        events = [_event("TASK_COMPLETED", {
            "deadline": (NOW + timedelta(hours=5)).isoformat(),
            "completed_at": NOW.isoformat(),
        })]
        result = await extract_platform_signals(events)
        for sig in result["signals"]:
            assert sig["event_type"] == "TASK_COMPLETED"


# ---------------------------------------------------------------------------
# Coverage of all 25+ event types
# ---------------------------------------------------------------------------


class TestAllEventTypes:
    """Ensure every mapped event type produces signals."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_type", [
        "MESSAGE_RESPONDED",
        "MESSAGE_SENT",
        "NOTIFICATION_OPENED",
        "TASK_COMPLETED",
        "TASK_OVERDUE",
        "TASK_STARTED",
        "MENTORSHIP_REQUESTED",
        "MENTORSHIP_COMPLETED",
        "MENTORSHIP_GIVEN",
        "QUESTION_POSTED",
        "QUESTION_ANSWERED",
        "ASSESSMENT_STARTED",
        "ASSESSMENT_COMPLETE",
        "ASSESSMENT_QUESTION_ANSWER",
        "PAGE_VIEW",
        "NAVIGATION",
        "CLICK",
        "SCROLL",
        "HOVER",
        "FORM_START",
        "FORM_SUBMIT",
        "FORM_ABANDON",
        "PROFILE_UPLOAD",
        "PROFILE_PARSE_COMPLETE",
        "PROFILE_UPDATED",
        "SESSION_START",
        "SESSION_END",
        "ERROR",
        "TIMEOUT",
        "CONNECTION_REQUESTED",
        "CONNECTION_ACCEPTED",
        "CONTENT_SHARED",
        "CONTENT_LIKED",
        "COMMENT_POSTED",
    ])
    async def test_event_type_produces_signals(self, event_type: str) -> None:
        events = [_event(event_type)]
        result = await extract_platform_signals(events)
        assert result["success"] is True
        assert result["signal_count"] > 0, f"{event_type} produced no signals"
        for sig in result["signals"]:
            assert sig["dimension"] in ("D", "I", "S", "C")
            assert isinstance(sig["weight"], float)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge-case handling."""

    @pytest.mark.asyncio
    async def test_payload_with_missing_optional_fields(self) -> None:
        """Context detectors should gracefully handle missing payload keys."""
        events = [_event("MESSAGE_RESPONDED", {})]
        result = await extract_platform_signals(events)
        assert result["success"] is True
        # Should still produce base signals, just no modifiers
        assert result["signal_count"] > 0

    @pytest.mark.asyncio
    async def test_latency_in_top_level_event(self) -> None:
        """Latency can be in top-level event dict (per validator)."""
        events = [_event("MESSAGE_RESPONDED", {}, latency_ms=100)]
        result = await extract_platform_signals(events)
        # Should detect fast_response from top-level latency_ms
        responded_signals = [
            s for s in result["signals"] if s["event_type"] == "MESSAGE_RESPONDED"
        ]
        assert any(
            "fast_response" in s["evidence"]["modifiers_applied"]
            for s in responded_signals
        )

    @pytest.mark.asyncio
    async def test_negative_weight_signals_included(self) -> None:
        """Events like TASK_OVERDUE produce negative weights."""
        events = [_event("TASK_OVERDUE")]
        result = await extract_platform_signals(events)
        assert result["success"] is True
        negative_signals = [s for s in result["signals"] if s["weight"] < 0]
        assert len(negative_signals) > 0

    @pytest.mark.asyncio
    async def test_large_batch(self) -> None:
        """Process a large batch without errors."""
        events = [_event("CLICK") for _ in range(100)]
        result = await extract_platform_signals(events)
        assert result["success"] is True
        assert result["signal_count"] == 200  # 2 signals per CLICK * 100
