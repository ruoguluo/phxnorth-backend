"""Tests for event ingestion API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_deduplicator, get_kafka_producer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_event(*, event_type: str = "MESSAGE_RESPONDED") -> dict:
    """Build a valid single event payload."""
    return {
        "user_id": str(uuid4()),
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"context": "test"},
    }


# ---------------------------------------------------------------------------
# Single event ingestion
# ---------------------------------------------------------------------------


class TestIngestSingleEvent:
    """Tests for POST /api/v1/events."""

    def test_ingest_single_event(self, app, client: TestClient) -> None:
        """Valid event is accepted with 202 and returns accepted=1."""
        # Events endpoint uses _require_auth (placeholder) so no real auth needed
        app.dependency_overrides[get_kafka_producer] = lambda: None
        app.dependency_overrides[get_deduplicator] = lambda: None

        try:
            event = _valid_event()
            response = client.post("/api/v1/events", json=event)

            assert response.status_code == 202
            data = response.json()
            assert data["accepted"] == 1
            assert data["rejected"] == 0
            assert len(data["event_ids"]) == 1
            assert data["rejected_details"] == []
        finally:
            app.dependency_overrides.clear()

    def test_ingest_event_with_optional_fields(self, app, client: TestClient) -> None:
        """Event with all optional fields is accepted."""
        app.dependency_overrides[get_kafka_producer] = lambda: None
        app.dependency_overrides[get_deduplicator] = lambda: None

        try:
            event = _valid_event()
            event["event_id"] = str(uuid4())
            event["session_id"] = str(uuid4())
            event["latency_ms"] = 150
            event["client_type"] = "web"

            response = client.post("/api/v1/events", json=event)

            assert response.status_code == 202
            data = response.json()
            assert data["accepted"] == 1
            assert data["rejected"] == 0
        finally:
            app.dependency_overrides.clear()

    def test_ingest_invalid_event(self, app, client: TestClient) -> None:
        """Event with unsupported event_type is rejected."""
        app.dependency_overrides[get_kafka_producer] = lambda: None
        app.dependency_overrides[get_deduplicator] = lambda: None

        try:
            event = _valid_event(event_type="TOTALLY_INVALID_EVENT_TYPE")

            response = client.post("/api/v1/events", json=event)

            assert response.status_code == 202  # endpoint always returns 202
            data = response.json()
            assert data["accepted"] == 0
            assert data["rejected"] == 1
            assert len(data["rejected_details"]) == 1
            assert len(data["rejected_details"][0]["errors"]) > 0
        finally:
            app.dependency_overrides.clear()

    def test_ingest_event_missing_required_fields(self, app, client: TestClient) -> None:
        """Event missing required fields is rejected with 422 by Pydantic."""
        app.dependency_overrides[get_kafka_producer] = lambda: None
        app.dependency_overrides[get_deduplicator] = lambda: None

        try:
            # Missing user_id, event_type, timestamp
            response = client.post("/api/v1/events", json={"payload": {}})
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Batch event ingestion
# ---------------------------------------------------------------------------


class TestIngestBatchEvents:
    """Tests for POST /api/v1/events/batch."""

    def test_ingest_batch_events(self, app, client: TestClient) -> None:
        """Batch of valid events is accepted."""
        app.dependency_overrides[get_kafka_producer] = lambda: None
        app.dependency_overrides[get_deduplicator] = lambda: None

        try:
            events = [_valid_event() for _ in range(3)]
            response = client.post("/api/v1/events/batch", json={"events": events})

            assert response.status_code == 202
            data = response.json()
            assert data["accepted"] == 3
            assert data["rejected"] == 0
            assert len(data["event_ids"]) == 3
        finally:
            app.dependency_overrides.clear()

    def test_ingest_batch_mixed_valid_invalid(self, app, client: TestClient) -> None:
        """Batch with mix of valid and invalid events correctly tallies both."""
        app.dependency_overrides[get_kafka_producer] = lambda: None
        app.dependency_overrides[get_deduplicator] = lambda: None

        try:
            events = [
                _valid_event(),
                _valid_event(event_type="TOTALLY_INVALID_TYPE"),
                _valid_event(),
            ]
            response = client.post("/api/v1/events/batch", json={"events": events})

            assert response.status_code == 202
            data = response.json()
            assert data["accepted"] == 2
            assert data["rejected"] == 1
            assert len(data["event_ids"]) == 2
            assert len(data["rejected_details"]) == 1
            # The rejected event was at index 1
            assert data["rejected_details"][0]["index"] == 1
        finally:
            app.dependency_overrides.clear()

    def test_batch_max_size(self, app, client: TestClient) -> None:
        """Batch exceeding 100 events is rejected with 422."""
        app.dependency_overrides[get_kafka_producer] = lambda: None
        app.dependency_overrides[get_deduplicator] = lambda: None

        try:
            events = [_valid_event() for _ in range(101)]
            response = client.post("/api/v1/events/batch", json={"events": events})

            # Pydantic max_length=100 on BatchEventsIn.events rejects > 100
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_batch_empty_events(self, app, client: TestClient) -> None:
        """Empty events list is rejected with 422 (min_length=1)."""
        app.dependency_overrides[get_kafka_producer] = lambda: None
        app.dependency_overrides[get_deduplicator] = lambda: None

        try:
            response = client.post("/api/v1/events/batch", json={"events": []})
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()
