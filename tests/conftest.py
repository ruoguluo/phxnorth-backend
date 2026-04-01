"""Test fixtures and configuration."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from starlette.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_application


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
