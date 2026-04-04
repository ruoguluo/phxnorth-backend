"""Tests for DISC profile API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, get_db, get_disc_cache
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user() -> MagicMock:
    """Return a mock User object with sensible defaults."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.is_active = True
    user.is_superuser = False
    return user


# ---------------------------------------------------------------------------
# DISC profile endpoint tests
# ---------------------------------------------------------------------------

USER_ID = str(uuid4())


class TestGetDISCProfile:
    """Tests for GET /api/v1/users/{user_id}/disc-profile."""

    def test_get_disc_profile(self, app, client: TestClient, auth_headers: dict) -> None:
        """Authenticated request returns a valid DISC profile with expected structure."""
        mock_user = _mock_user()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_disc_cache] = lambda: None

        try:
            response = client.get(
                f"/api/v1/users/{USER_ID}/disc-profile",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert data["user_id"] == USER_ID
            assert "scores" in data
            assert "D" in data["scores"]
            assert "I" in data["scores"]
            assert "S" in data["scores"]
            assert "C" in data["scores"]
            assert "dominant" in data
            assert "secondary" in data
            assert "confidence" in data
            assert "computed_at" in data
            assert "window" in data
            assert "data_sources" in data

            # Verify score ranges
            for dim in ("D", "I", "S", "C"):
                assert 0 <= data["scores"][dim] <= 100

            # Verify confidence range
            assert 0 <= data["confidence"] <= 1

            # Default window should be 90d
            assert data["window"] == "90d"
        finally:
            app.dependency_overrides.clear()

    def test_get_disc_profile_with_window(self, app, client: TestClient, auth_headers: dict) -> None:
        """Requesting ?window=30d returns profile with that window value."""
        mock_user = _mock_user()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_disc_cache] = lambda: None

        try:
            response = client.get(
                f"/api/v1/users/{USER_ID}/disc-profile?window=30d",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["window"] == "30d"
            assert data["user_id"] == USER_ID
        finally:
            app.dependency_overrides.clear()

    def test_get_disc_profile_lifetime_window(self, app, client: TestClient, auth_headers: dict) -> None:
        """Requesting ?window=lifetime returns profile with lifetime window."""
        mock_user = _mock_user()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_disc_cache] = lambda: None

        try:
            response = client.get(
                f"/api/v1/users/{USER_ID}/disc-profile?window=lifetime",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["window"] == "lifetime"
        finally:
            app.dependency_overrides.clear()

    def test_get_disc_profile_invalid_window(self, app, client: TestClient, auth_headers: dict) -> None:
        """Requesting an invalid window value returns 422."""
        mock_user = _mock_user()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_disc_cache] = lambda: None

        try:
            response = client.get(
                f"/api/v1/users/{USER_ID}/disc-profile?window=7d",
                headers=auth_headers,
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_get_disc_profile_unauthenticated(self, client: TestClient) -> None:
        """Request without auth headers returns 401 or 403."""
        response = client.get(f"/api/v1/users/{USER_ID}/disc-profile")
        # OAuth2 scheme returns 401 when no token is provided
        assert response.status_code in (401, 403)


class TestGetDISCHistory:
    """Tests for GET /api/v1/users/{user_id}/disc-profile/history."""

    def test_get_disc_history(self, app, client: TestClient, auth_headers: dict) -> None:
        """Authenticated request returns DISC profile history with expected structure."""
        mock_user = _mock_user()
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            response = client.get(
                f"/api/v1/users/{USER_ID}/disc-profile/history",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            assert data["user_id"] == USER_ID
            assert "history" in data
            assert isinstance(data["history"], list)
            assert len(data["history"]) > 0

            # Verify each history entry has expected structure
            for entry in data["history"]:
                assert "computed_at" in entry
                assert "scores" in entry
                assert "dominant" in entry
                for dim in ("D", "I", "S", "C"):
                    assert dim in entry["scores"]
                    assert 0 <= entry["scores"][dim] <= 100
        finally:
            app.dependency_overrides.clear()

    def test_get_disc_history_with_window(self, app, client: TestClient, auth_headers: dict) -> None:
        """History endpoint accepts window parameter."""
        mock_user = _mock_user()
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            response = client.get(
                f"/api/v1/users/{USER_ID}/disc-profile/history?window=30d",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data["history"], list)
        finally:
            app.dependency_overrides.clear()

    def test_get_disc_history_unauthenticated(self, client: TestClient) -> None:
        """History request without auth returns 401 or 403."""
        response = client.get(f"/api/v1/users/{USER_ID}/disc-profile/history")
        assert response.status_code in (401, 403)
