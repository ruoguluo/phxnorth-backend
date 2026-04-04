"""Test fixtures and configuration."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from starlette.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_application


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Settings & application
# ---------------------------------------------------------------------------

@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with testing environment."""
    return Settings(
        environment="testing",
        debug=True,
        log_level="DEBUG",
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_phxnorth",
        redis_url="redis://localhost:6379/1",
        secret_key="test-secret-key",
    )


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    """Create a FastAPI application for testing."""
    application = create_application()
    
    # Override settings dependency
    application.dependency_overrides[get_settings] = lambda: test_settings
    
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a synchronous test client."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an asynchronous test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers(test_settings: Settings) -> dict:
    """JWT auth headers for a regular user (mentee role)."""
    from app.core.security import create_access_token

    token = create_access_token({"sub": "test-user-uuid", "role": "mentee"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_settings: Settings) -> dict:
    """JWT auth headers for an admin user."""
    from app.core.security import create_access_token

    token = create_access_token({"sub": "admin-user-uuid", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mentor_auth_headers(test_settings: Settings) -> dict:
    """JWT auth headers for a mentor user."""
    from app.core.security import create_access_token

    token = create_access_token({"sub": "mentor-user-uuid", "role": "mentor"})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Mock Kafka producer
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_kafka_producer() -> AsyncMock:
    """Mock Kafka producer that records sent messages.

    The mock tracks every message passed to ``send`` or ``send_batch`` in the
    ``messages`` list so tests can assert on published events.
    """
    producer = AsyncMock()
    producer.messages: list[dict[str, Any]] = []  # type: ignore[assignment]

    async def _capture_send(topic: str, message: dict, key: str | None = None) -> None:
        producer.messages.append({"topic": topic, "message": message, "key": key})

    async def _capture_send_batch(
        topic: str, messages: list[dict], key: str | None = None
    ) -> None:
        for msg in messages:
            producer.messages.append({"topic": topic, "message": msg, "key": key})

    producer.send = AsyncMock(side_effect=_capture_send)
    producer.send_batch = AsyncMock(side_effect=_capture_send_batch)
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    return producer


# ---------------------------------------------------------------------------
# Mock Redis (in-memory dict-based)
# ---------------------------------------------------------------------------

class MockRedisCache:
    """In-memory mock implementing the RedisCacheService interface.

    Backed by a plain dict so tests can run without a real Redis instance.
    TTL values are recorded but not enforced (tests are instantaneous).
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    # Lifecycle ---------------------------------------------------------
    async def connect(self) -> None:  # noqa: D102
        pass

    async def disconnect(self) -> None:  # noqa: D102
        pass

    # Basic get / set / delete -----------------------------------------
    async def get(self, key: str) -> str | None:  # noqa: D102
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:  # noqa: D102
        self._store[key] = value
        if ttl_seconds is not None:
            self._ttls[key] = ttl_seconds

    async def delete(self, key: str) -> None:  # noqa: D102
        self._store.pop(key, None)
        self._ttls.pop(key, None)

    async def exists(self, key: str) -> bool:  # noqa: D102
        return key in self._store

    # JSON helpers -----------------------------------------------------
    async def get_json(self, key: str) -> dict[str, Any] | None:  # noqa: D102
        raw = self._store.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(
        self, key: str, value: dict[str, Any], ttl_seconds: int | None = None
    ) -> None:  # noqa: D102
        await self.set(key, json.dumps(value, default=str), ttl_seconds)

    # Atomic helpers ---------------------------------------------------
    async def set_if_not_exists(self, key: str, value: str, ttl_seconds: int) -> bool:  # noqa: D102
        if key in self._store:
            return False
        self._store[key] = value
        self._ttls[key] = ttl_seconds
        return True

    # Pattern operations -----------------------------------------------
    async def get_keys(self, pattern: str) -> list[str]:  # noqa: D102
        import fnmatch

        return [k for k in self._store if fnmatch.fnmatch(k, pattern)]

    async def delete_pattern(self, pattern: str) -> int:  # noqa: D102
        import fnmatch

        keys_to_delete = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
        for k in keys_to_delete:
            self._store.pop(k, None)
            self._ttls.pop(k, None)
        return len(keys_to_delete)


@pytest.fixture
def mock_redis() -> MockRedisCache:
    """In-memory mock Redis implementing the RedisCacheService interface."""
    return MockRedisCache()


# ---------------------------------------------------------------------------
# Mock async DB session
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock async SQLAlchemy session for unit tests.

    Provides the common async session methods (execute, commit, rollback,
    refresh, close) as ``AsyncMock`` instances.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_event() -> dict[str, Any]:
    """Sample behavioral event for testing."""
    return {
        "event_id": "evt-001",
        "user_id": "test-user-uuid",
        "session_id": "sess-abc-123",
        "event_type": "page_view",
        "payload": {
            "page": "/dashboard",
            "duration_ms": 4500,
            "scroll_depth": 0.85,
        },
        "latency_ms": 120,
        "client_type": "web",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def sample_disc_profile() -> dict[str, Any]:
    """Sample DISC profile result as a plain dict (API-style representation)."""
    return {
        "user_id": "test-user-uuid",
        "d_score": 72.5,
        "i_score": 58.0,
        "s_score": 45.0,
        "c_score": 81.0,
        "dominant": "C",
        "secondary": "D",
        "confidence": 0.89,
        "signal_count": 134,
        "contradiction_score": 0.12,
        "shift_magnitude": 0.04,
        "shift_type": "stable",
        "model_version": "1.0",
        "window_days": 30,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def sample_risk_result() -> dict[str, Any]:
    """Sample risk assessment result as a plain dict."""
    return {
        "user_id": "test-user-uuid",
        "category": "career_volatility",
        "score": 0.42,
        "severity": "yellow",
        "is_flagged": True,
        "evidence": {
            "short_tenures": 2,
            "avg_tenure_months": 14.5,
            "threshold": 0.40,
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def sample_signal() -> dict[str, Any]:
    """Sample DISC signal extracted from behavioral data."""
    return {
        "signal_id": "sig-001",
        "user_id": "test-user-uuid",
        "signal_type": "D",
        "confidence": 0.78,
        "source": "platform_behavior",
        "evidence": {
            "event_type": "rapid_decision",
            "context": "Quick project selection",
        },
        "ttl_days": 30,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def sample_cv_upload() -> dict[str, Any]:
    """Sample CV upload event payload."""
    return {
        "event_id": "cv-001",
        "user_id": "test-user-uuid",
        "source": "upload",
        "s3_key": "uploads/test-user-uuid/resume.pdf",
        "raw_text": "John Doe\nSenior Software Engineer\n5 years experience...",
        "filename": "resume.pdf",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def sample_red_flag() -> dict[str, Any]:
    """Sample red flag event as a plain dict."""
    return {
        "user_id": "test-user-uuid",
        "flag_type": "high_volatility",
        "severity": "orange",
        "description": "Career shows high volatility pattern",
        "metadata": {"threshold": 0.7, "actual": 0.85},
        "resolved": False,
    }
