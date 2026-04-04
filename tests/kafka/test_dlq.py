"""Tests for the Dead Letter Queue handler."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.kafka.dlq import DLQ_SUFFIX, DeadLetterQueue


# ---- helpers ----------------------------------------------------------------


class FakeProducer:
    """In-memory producer that records sent messages."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.messages: list[dict[str, Any]] = []
        self._should_fail = should_fail

    async def send(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
    ) -> None:
        if self._should_fail:
            raise RuntimeError("broker unavailable")
        self.messages.append({"topic": topic, "value": value, "key": key})


# ---- get_dlq_topic ----------------------------------------------------------


class TestGetDlqTopic:
    """Verify DLQ topic naming convention."""

    def test_appends_dlq_suffix(self) -> None:
        assert DeadLetterQueue.get_dlq_topic("raw.cv.uploads") == "raw.cv.uploads.dlq"

    def test_signals_topic(self) -> None:
        assert DeadLetterQueue.get_dlq_topic("signals.cv") == "signals.cv.dlq"

    def test_behavioral_events(self) -> None:
        assert (
            DeadLetterQueue.get_dlq_topic("raw.behavioral.events")
            == "raw.behavioral.events.dlq"
        )

    def test_signals_platform(self) -> None:
        assert (
            DeadLetterQueue.get_dlq_topic("signals.platform")
            == "signals.platform.dlq"
        )

    def test_arbitrary_topic(self) -> None:
        assert DeadLetterQueue.get_dlq_topic("my.custom.topic") == "my.custom.topic.dlq"

    def test_suffix_constant(self) -> None:
        assert DLQ_SUFFIX == ".dlq"


# ---- send_to_dlq -----------------------------------------------------------


class TestSendToDlq:
    """Verify messages are correctly routed to DLQ topics."""

    @pytest.mark.asyncio
    async def test_sends_to_correct_dlq_topic(self) -> None:
        producer = FakeProducer()
        dlq = DeadLetterQueue(producer)

        await dlq.send_to_dlq(
            original_topic="raw.cv.uploads",
            message={"user_id": "u1", "cv_url": "https://example.com/cv.pdf"},
            error="PDF extraction failed",
            retry_count=3,
        )

        assert len(producer.messages) == 1
        assert producer.messages[0]["topic"] == "raw.cv.uploads.dlq"

    @pytest.mark.asyncio
    async def test_wraps_message_with_metadata(self) -> None:
        producer = FakeProducer()
        dlq = DeadLetterQueue(producer)
        original = {"user_id": "u1", "data": [1, 2, 3]}

        await dlq.send_to_dlq(
            original_topic="signals.cv",
            message=original,
            error="schema validation failed",
            retry_count=5,
            original_key="u1",
        )

        envelope = producer.messages[0]["value"]
        assert envelope["original_topic"] == "signals.cv"
        assert envelope["original_message"] == original
        assert envelope["error"] == "schema validation failed"
        assert envelope["retry_count"] == 5
        assert envelope["original_key"] == "u1"

    @pytest.mark.asyncio
    async def test_failed_at_is_iso_timestamp(self) -> None:
        producer = FakeProducer()
        dlq = DeadLetterQueue(producer)

        before = datetime.now(timezone.utc)
        await dlq.send_to_dlq(
            original_topic="raw.behavioral.events",
            message={"event": "click"},
            error="timeout",
            retry_count=2,
        )
        after = datetime.now(timezone.utc)

        failed_at = datetime.fromisoformat(
            producer.messages[0]["value"]["failed_at"]
        )
        assert before <= failed_at <= after

    @pytest.mark.asyncio
    async def test_original_key_is_none_by_default(self) -> None:
        producer = FakeProducer()
        dlq = DeadLetterQueue(producer)

        await dlq.send_to_dlq(
            original_topic="signals.platform",
            message={"foo": "bar"},
            error="processing error",
            retry_count=1,
        )

        envelope = producer.messages[0]["value"]
        assert envelope["original_key"] is None

    @pytest.mark.asyncio
    async def test_preserves_original_key_on_producer_call(self) -> None:
        producer = FakeProducer()
        dlq = DeadLetterQueue(producer)

        await dlq.send_to_dlq(
            original_topic="raw.cv.uploads",
            message={"data": "value"},
            error="bad format",
            retry_count=3,
            original_key="key-123",
        )

        assert producer.messages[0]["key"] == "key-123"

    @pytest.mark.asyncio
    async def test_envelope_has_all_required_keys(self) -> None:
        producer = FakeProducer()
        dlq = DeadLetterQueue(producer)

        await dlq.send_to_dlq(
            original_topic="raw.cv.uploads",
            message={"x": 1},
            error="err",
            retry_count=0,
        )

        expected_keys = {
            "original_topic",
            "original_message",
            "error",
            "retry_count",
            "failed_at",
            "original_key",
        }
        assert set(producer.messages[0]["value"].keys()) == expected_keys


# ---- error handling ---------------------------------------------------------


class TestDlqErrorHandling:
    """Verify behaviour when the DLQ producer itself fails."""

    @pytest.mark.asyncio
    async def test_raises_when_producer_fails(self) -> None:
        producer = FakeProducer(should_fail=True)
        dlq = DeadLetterQueue(producer)

        with pytest.raises(RuntimeError, match="broker unavailable"):
            await dlq.send_to_dlq(
                original_topic="raw.cv.uploads",
                message={"x": 1},
                error="err",
                retry_count=1,
            )

    @pytest.mark.asyncio
    async def test_no_message_sent_on_failure(self) -> None:
        producer = FakeProducer(should_fail=True)
        dlq = DeadLetterQueue(producer)

        with pytest.raises(RuntimeError):
            await dlq.send_to_dlq(
                original_topic="raw.cv.uploads",
                message={"x": 1},
                error="err",
                retry_count=1,
            )

        assert len(producer.messages) == 0
