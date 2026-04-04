"""Tests for Behavioral models."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.behavioral import BehavioralEvent, BehavioralMetrics, ClientType, EventType
from app.models.user import User


class TestBehavioralEventInstantiation:
    """Test BehavioralEvent model instantiation."""

    async def test_behavioral_event_can_be_created(self, db_session: AsyncSession, sample_user_data, sample_behavioral_event_data):
        """Test that a behavioral event can be created."""
        # Create user first
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        # Create behavioral event
        event = BehavioralEvent(
            user_id=user.id,
            **sample_behavioral_event_data,
        )
        db_session.add(event)
        await db_session.commit()

        assert event.id is not None
        assert isinstance(event.id, uuid.UUID)
        assert event.user_id == user.id
        assert event.event_type == EventType.PAGE_VIEW
        assert event.payload == sample_behavioral_event_data["payload"]

    async def test_behavioral_event_has_created_at(self, db_session: AsyncSession, sample_user_data):
        """Test that behavioral event has created_at timestamp."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = BehavioralEvent(
            user_id=user.id,
            event_type=EventType.CLICK,
            payload={"element": "button"},
        )
        db_session.add(event)
        await db_session.commit()

        assert event.created_at is not None
        assert isinstance(event.created_at, datetime)

    async def test_behavioral_event_payload_defaults_to_empty_dict(self, db_session: AsyncSession, sample_user_data):
        """Test that payload defaults to empty dict."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = BehavioralEvent(
            user_id=user.id,
            event_type=EventType.SESSION_START,
        )
        db_session.add(event)
        await db_session.commit()

        assert event.payload == {}


class TestBehavioralEventConstraints:
    """Test BehavioralEvent model constraints."""

    async def test_user_id_is_required(self, db_session: AsyncSession):
        """Test that user_id cannot be null."""
        event = BehavioralEvent(
            user_id=None,
            event_type=EventType.PAGE_VIEW,
            payload={},
        )
        db_session.add(event)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_event_type_is_required(self, db_session: AsyncSession, sample_user_data):
        """Test that event_type cannot be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = BehavioralEvent(
            user_id=user.id,
            event_type=None,
            payload={},
        )
        db_session.add(event)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_payload_is_required(self, db_session: AsyncSession, sample_user_data):
        """Test that payload cannot be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = BehavioralEvent(
            user_id=user.id,
            event_type=EventType.PAGE_VIEW,
            payload=None,
        )
        db_session.add(event)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_session_id_can_be_null(self, db_session: AsyncSession, sample_user_data):
        """Test that session_id can be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = BehavioralEvent(
            user_id=user.id,
            event_type=EventType.PAGE_VIEW,
            payload={},
            session_id=None,
        )
        db_session.add(event)
        await db_session.commit()

        assert event.session_id is None

    async def test_latency_ms_can_be_null(self, db_session: AsyncSession, sample_user_data):
        """Test that latency_ms can be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = BehavioralEvent(
            user_id=user.id,
            event_type=EventType.PAGE_VIEW,
            payload={},
            latency_ms=None,
        )
        db_session.add(event)
        await db_session.commit()

        assert event.latency_ms is None

    async def test_client_type_can_be_null(self, db_session: AsyncSession, sample_user_data):
        """Test that client_type can be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = BehavioralEvent(
            user_id=user.id,
            event_type=EventType.PAGE_VIEW,
            payload={},
            client_type=None,
        )
        db_session.add(event)
        await db_session.commit()

        assert event.client_type is None


class TestBehavioralEventEnumValidation:
    """Test BehavioralEvent enum validation."""

    async def test_event_type_enum_values(self, db_session: AsyncSession, sample_user_data):
        """Test that EventType enum values work correctly."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event_types = [
            EventType.PAGE_VIEW,
            EventType.NAVIGATION,
            EventType.CLICK,
            EventType.HOVER,
            EventType.SCROLL,
            EventType.FORM_START,
            EventType.FORM_SUBMIT,
            EventType.FORM_ABANDON,
            EventType.ASSESSMENT_START,
            EventType.ASSESSMENT_COMPLETE,
            EventType.ASSESSMENT_QUESTION_ANSWER,
            EventType.PROFILE_UPLOAD,
            EventType.PROFILE_PARSE_COMPLETE,
            EventType.MESSAGE_SENT,
            EventType.NOTIFICATION_OPENED,
            EventType.SESSION_START,
            EventType.SESSION_END,
            EventType.ERROR,
            EventType.TIMEOUT,
        ]

        for event_type in event_types:
            event = BehavioralEvent(
                user_id=user.id,
                event_type=event_type,
                payload={"test": True},
            )
            db_session.add(event)

        await db_session.commit()

        result = await db_session.execute(
            select(BehavioralEvent).where(BehavioralEvent.user_id == user.id)
        )
        events = result.scalars().all()
        assert len(events) == len(event_types)

    async def test_client_type_enum_values(self, db_session: AsyncSession, sample_user_data):
        """Test that ClientType enum values work correctly."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        client_types = [
            ClientType.WEB,
            ClientType.MOBILE,
            ClientType.DESKTOP,
            ClientType.API,
        ]

        for i, client_type in enumerate(client_types):
            event = BehavioralEvent(
                user_id=user.id,
                event_type=EventType.PAGE_VIEW,
                payload={"client_index": i},
                client_type=client_type,
            )
            db_session.add(event)

        await db_session.commit()

        result = await db_session.execute(
            select(BehavioralEvent).where(BehavioralEvent.user_id == user.id)
        )
        events = result.scalars().all()
        assert len(events) == 4


class TestBehavioralEventJSONField:
    """Test BehavioralEvent JSON field handling."""

    async def test_payload_stores_complex_json(self, db_session: AsyncSession, sample_user_data):
        """Test that payload can store complex JSON data."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        complex_payload = {
            "nested": {
                "deep": {
                    "value": 123,
                },
            },
            "array": [1, 2, 3, "four", "five"],
            "boolean": True,
            "null_value": None,
            "number": 42.5,
        }

        event = BehavioralEvent(
            user_id=user.id,
            event_type=EventType.PAGE_VIEW,
            payload=complex_payload,
        )
        db_session.add(event)
        await db_session.commit()

        # Refresh to get from DB
        await db_session.refresh(event)
        assert event.payload == complex_payload

    async def test_payload_stores_string_values(self, db_session: AsyncSession, sample_user_data):
        """Test that payload can store string values."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = BehavioralEvent(
            user_id=user.id,
            event_type=EventType.NAVIGATION,
            payload={"from_page": "/home", "to_page": "/profile"},
        )
        db_session.add(event)
        await db_session.commit()

        await db_session.refresh(event)
        assert event.payload["from_page"] == "/home"
        assert event.payload["to_page"] == "/profile"


class TestBehavioralMetricsInstantiation:
    """Test BehavioralMetrics model instantiation."""

    async def test_behavioral_metrics_can_be_created(self, db_session: AsyncSession, sample_user_data):
        """Test that behavioral metrics can be created."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        metrics = BehavioralMetrics(
            user_id=user.id,
            metric_type="page_views_per_session",
            metric_value=15.5,
            window_days=30,
            sample_count=100,
            computed_at=datetime.utcnow(),
        )
        db_session.add(metrics)
        await db_session.commit()

        assert metrics.id is not None
        assert metrics.user_id == user.id
        assert metrics.metric_type == "page_views_per_session"
        assert metrics.metric_value == 15.5

    async def test_behavioral_metrics_has_created_at(self, db_session: AsyncSession, sample_user_data):
        """Test that behavioral metrics has created_at timestamp."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        metrics = BehavioralMetrics(
            user_id=user.id,
            metric_type="test_metric",
            metric_value=1.0,
            window_days=7,
            computed_at=datetime.utcnow(),
        )
        db_session.add(metrics)
        await db_session.commit()

        assert metrics.created_at is not None
        assert isinstance(metrics.created_at, datetime)


class TestBehavioralMetricsConstraints:
    """Test BehavioralMetrics model constraints."""

    async def test_user_id_metric_type_window_unique(self, db_session: AsyncSession, sample_user_data):
        """Test that user_id, metric_type, window_days combination must be unique."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        metrics1 = BehavioralMetrics(
            user_id=user.id,
            metric_type="test_metric",
            metric_value=1.0,
            window_days=30,
            computed_at=datetime.utcnow(),
        )
        db_session.add(metrics1)
        await db_session.commit()

        metrics2 = BehavioralMetrics(
            user_id=user.id,
            metric_type="test_metric",
            metric_value=2.0,
            window_days=30,
            computed_at=datetime.utcnow(),
        )
        db_session.add(metrics2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_metric_value_is_required(self, db_session: AsyncSession, sample_user_data):
        """Test that metric_value cannot be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        metrics = BehavioralMetrics(
            user_id=user.id,
            metric_type="test_metric",
            metric_value=None,
            window_days=30,
            computed_at=datetime.utcnow(),
        )
        db_session.add(metrics)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    async def test_sample_count_can_be_null(self, db_session: AsyncSession, sample_user_data):
        """Test that sample_count can be null."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        metrics = BehavioralMetrics(
            user_id=user.id,
            metric_type="test_metric",
            metric_value=1.0,
            window_days=30,
            sample_count=None,
            computed_at=datetime.utcnow(),
        )
        db_session.add(metrics)
        await db_session.commit()

        assert metrics.sample_count is None


class TestBehavioralModelRepresentation:
    """Test Behavioral model string representations."""

    async def test_behavioral_event_repr(self, db_session: AsyncSession, sample_user_data):
        """Test BehavioralEvent __repr__ method."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        event = BehavioralEvent(
            user_id=user.id,
            event_type=EventType.PAGE_VIEW,
            payload={"page": "/test"},
        )
        db_session.add(event)
        await db_session.commit()

        repr_str = repr(event)
        assert "BehavioralEvent" in repr_str
        assert str(event.id) in repr_str
        assert "page_view" in repr_str

    async def test_behavioral_metrics_repr(self, db_session: AsyncSession, sample_user_data):
        """Test BehavioralMetrics __repr__ method."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.commit()

        metrics = BehavioralMetrics(
            user_id=user.id,
            metric_type="test_metric",
            metric_value=1.0,
            window_days=30,
            computed_at=datetime.utcnow(),
        )
        db_session.add(metrics)
        await db_session.commit()

        repr_str = repr(metrics)
        assert "BehavioralMetrics" in repr_str
        assert str(user.id) in repr_str
        assert "test_metric" in repr_str
