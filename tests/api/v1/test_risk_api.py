"""Tests for risk assessment, contradiction, and behavioral-shift API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, get_risk_cache
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


USER_ID = str(uuid4())


# ---------------------------------------------------------------------------
# Risk assessment tests
# ---------------------------------------------------------------------------


class TestGetRiskAssessment:
    """Tests for GET /api/v1/users/{user_id}/risk."""

    def test_get_risk_assessment(self, app, client: TestClient, auth_headers: dict) -> None:
        """Authenticated request returns a valid risk assessment with expected structure."""
        mock_user = _mock_user()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_risk_cache] = lambda: None

        try:
            response = client.get(
                f"/api/v1/users/{USER_ID}/risk",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert data["user_id"] == USER_ID
            assert "computed_at" in data
            assert "overall_risk_tier" in data
            assert data["overall_risk_tier"] in ("low", "medium", "high", "critical")
            assert "assessments" in data
            assert isinstance(data["assessments"], list)
            assert "active_flags" in data
            assert isinstance(data["active_flags"], list)

            # Verify assessment items structure
            for item in data["assessments"]:
                assert "category" in item
                assert "score" in item
                assert 0 <= item["score"] <= 1
                assert "severity" in item
                assert "description" in item

            # Verify flag structure
            for flag in data["active_flags"]:
                assert "flag_id" in flag
                assert "category" in flag
                assert "raised_at" in flag
                assert "message" in flag
        finally:
            app.dependency_overrides.clear()

    def test_get_risk_assessment_unauthenticated(self, client: TestClient) -> None:
        """Risk assessment without auth returns 401 or 403."""
        response = client.get(f"/api/v1/users/{USER_ID}/risk")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Contradiction analysis tests
# ---------------------------------------------------------------------------


class TestGetContradiction:
    """Tests for GET /api/v1/users/{user_id}/contradiction."""

    def test_get_contradiction(self, app, client: TestClient, auth_headers: dict) -> None:
        """Authenticated request returns a valid contradiction analysis."""
        mock_user = _mock_user()
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            response = client.get(
                f"/api/v1/users/{USER_ID}/contradiction",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert data["user_id"] == USER_ID
            assert "contradiction_score" in data
            assert 0 <= data["contradiction_score"] <= 1
            assert "severity_tier" in data
            assert data["severity_tier"] in ("none", "low", "medium", "high")
            assert "threshold_exceeded" in data
            assert isinstance(data["threshold_exceeded"], bool)
            assert "dimension_gaps" in data
            assert isinstance(data["dimension_gaps"], list)
            assert "flagged_dimensions" in data
            assert isinstance(data["flagged_dimensions"], list)

            # Verify dimension gap structure
            for gap in data["dimension_gaps"]:
                assert "dimension_a" in gap
                assert "dimension_b" in gap
                assert "gap" in gap
                assert "interpretation" in gap
        finally:
            app.dependency_overrides.clear()

    def test_get_contradiction_unauthenticated(self, client: TestClient) -> None:
        """Contradiction analysis without auth returns 401 or 403."""
        response = client.get(f"/api/v1/users/{USER_ID}/contradiction")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Behavioral shift tests
# ---------------------------------------------------------------------------


class TestGetBehavioralShift:
    """Tests for GET /api/v1/users/{user_id}/behavioral-shift."""

    def test_get_behavioral_shift(self, app, client: TestClient, auth_headers: dict) -> None:
        """Authenticated request returns a valid behavioral shift analysis."""
        mock_user = _mock_user()
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            response = client.get(
                f"/api/v1/users/{USER_ID}/behavioral-shift",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert data["user_id"] == USER_ID
            assert "shift_detected" in data
            assert isinstance(data["shift_detected"], bool)
            assert "magnitude" in data
            assert 0 <= data["magnitude"] <= 1
            assert "shift_type" in data  # can be None
            assert "shifted_dimensions" in data
            assert isinstance(data["shifted_dimensions"], list)
            assert "interpretation" in data
        finally:
            app.dependency_overrides.clear()

    def test_get_behavioral_shift_unauthenticated(self, client: TestClient) -> None:
        """Behavioral shift without auth returns 401 or 403."""
        response = client.get(f"/api/v1/users/{USER_ID}/behavioral-shift")
        assert response.status_code in (401, 403)
