"""Tests for health check endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient


class TestRootEndpoint:
    """Tests for the root endpoint."""

    def test_root_returns_api_info(self, client: TestClient) -> None:
        """Test that root endpoint returns basic API information."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "environment" in data
        assert data["name"] == "PhxNorth Backend"
        assert data["environment"] == "testing"

    @pytest.mark.asyncio
    async def test_root_async(self, async_client: AsyncClient) -> None:
        """Test root endpoint with async client."""
        response = await async_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check_returns_healthy(self, client: TestClient) -> None:
        """Test that health endpoint returns healthy status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestReadinessProbe:
    """Tests for the Kubernetes readiness probe."""

    @pytest.mark.asyncio
    async def test_ready_with_mock_db(self, async_client: AsyncClient) -> None:
        """Test readiness probe with mocked database."""
        # Mock the database session
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute.return_value = mock_result
        
        # Patch the get_db dependency
        from app.api.v1.health import get_db
        
        def override_get_db():
            return mock_db
        
        async_client.app.dependency_overrides[get_db] = override_get_db
        
        try:
            response = await async_client.get("/api/v1/ready")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
        finally:
            # Clean up override
            async_client.app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_ready_with_db_error(self, async_client: AsyncClient) -> None:
        """Test readiness probe when database is unavailable."""
        from app.api.v1.health import get_db
        
        # Mock the database to raise an exception
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute.side_effect = Exception("Connection refused")
        
        def override_get_db():
            return mock_db
        
        async_client.app.dependency_overrides[get_db] = override_get_db
        
        try:
            response = await async_client.get("/api/v1/ready")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "not ready"
            assert "database" in data["reason"].lower()
        finally:
            # Clean up override
            async_client.app.dependency_overrides.pop(get_db, None)


class TestLivenessProbe:
    """Tests for the Kubernetes liveness probe."""

    @pytest.mark.asyncio
    async def test_live_returns_alive(self, async_client: AsyncClient) -> None:
        """Test that liveness probe returns alive status."""
        response = await async_client.get("/api/v1/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    def test_live_sync(self, client: TestClient) -> None:
        """Test liveness probe with sync client."""
        response = client.get("/api/v1/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
