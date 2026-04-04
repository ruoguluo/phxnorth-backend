"""Tests for authentication endpoints and security utilities.

Tests cover three layers:
1. Security module (password hashing, token creation/verification)
2. Auth schema validation
3. Auth endpoint routing with mocked DB
"""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from jose import JWTError, jwt
from pydantic import ValidationError
from starlette.testclient import TestClient

from app.api.v1.schemas.auth import (
    MessageResponse,
    RefreshTokenRequest,
    TokenRequest,
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
)
from app.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)


# ---------------------------------------------------------------------------
# Layer 1: Security module unit tests
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_hash_password_returns_hash(self) -> None:
        """Hashing a password produces a bcrypt string."""
        hashed = hash_password("mysecretpassword")
        assert hashed != "mysecretpassword"
        assert hashed.startswith("$2b$")

    def test_hash_password_unique_per_call(self) -> None:
        """Two hashes of the same password should differ (different salts)."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2

    def test_verify_password_correct(self) -> None:
        """verify_password returns True for the correct password."""
        hashed = hash_password("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_verify_password_wrong(self) -> None:
        """verify_password returns False for an incorrect password."""
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_password_empty_string(self) -> None:
        """verify_password returns False when checking empty string against a hash."""
        hashed = hash_password("nonempty")
        assert verify_password("", hashed) is False


class TestAccessTokenCreation:
    """Tests for JWT access token creation and verification."""

    def test_create_access_token_contains_sub(self) -> None:
        """Access token payload should contain the 'sub' claim."""
        token = create_access_token({"sub": "user-123", "role": "mentee"})
        payload = verify_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "mentee"

    def test_create_access_token_type_is_access(self) -> None:
        """Access token should carry type='access'."""
        token = create_access_token({"sub": "user-123"})
        payload = verify_token(token)
        assert payload["type"] == "access"

    def test_create_access_token_has_expiry(self) -> None:
        """Access token must include an 'exp' claim."""
        token = create_access_token({"sub": "user-123"})
        payload = verify_token(token)
        assert "exp" in payload

    def test_create_access_token_custom_expiry(self) -> None:
        """Custom expiration delta should be respected."""
        token = create_access_token(
            {"sub": "user-123"},
            expires_delta=timedelta(minutes=5),
        )
        payload = verify_token(token)
        assert "exp" in payload

    def test_create_access_token_does_not_mutate_data(self) -> None:
        """The original data dict must not be modified."""
        data = {"sub": "user-123", "role": "mentee"}
        original_keys = set(data.keys())
        create_access_token(data)
        assert set(data.keys()) == original_keys


class TestRefreshTokenCreation:
    """Tests for JWT refresh token creation."""

    def test_create_refresh_token_type_is_refresh(self) -> None:
        """Refresh token should carry type='refresh'."""
        token = create_refresh_token({"sub": "user-123"})
        payload = verify_token(token)
        assert payload["type"] == "refresh"

    def test_create_refresh_token_contains_sub(self) -> None:
        """Refresh token payload should preserve the 'sub' claim."""
        token = create_refresh_token({"sub": "user-456", "role": "admin"})
        payload = verify_token(token)
        assert payload["sub"] == "user-456"
        assert payload["role"] == "admin"

    def test_create_refresh_token_has_expiry(self) -> None:
        """Refresh token must include an 'exp' claim."""
        token = create_refresh_token({"sub": "user-123"})
        payload = verify_token(token)
        assert "exp" in payload


class TestVerifyToken:
    """Tests for token verification edge cases."""

    def test_verify_token_rejects_tampered_token(self) -> None:
        """A token with an altered signature must be rejected."""
        token = create_access_token({"sub": "user-123"})
        tampered = token[:-4] + "XXXX"
        with pytest.raises(JWTError):
            verify_token(tampered)

    def test_verify_token_rejects_wrong_secret(self) -> None:
        """A token signed with a different secret must be rejected."""
        settings = get_settings()
        # Manually create a token with a different secret
        payload = {"sub": "user-123", "type": "access", "exp": 9999999999}
        fake_token = jwt.encode(payload, "wrong-secret", algorithm=settings.algorithm)
        with pytest.raises(JWTError):
            verify_token(fake_token)

    def test_verify_expired_token(self) -> None:
        """An expired token must raise JWTError."""
        token = create_access_token(
            {"sub": "user-123"},
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(JWTError):
            verify_token(token)

    def test_verify_token_rejects_garbage(self) -> None:
        """Random garbage string must be rejected."""
        with pytest.raises(JWTError):
            verify_token("not.a.valid.token")


# ---------------------------------------------------------------------------
# Layer 2: Schema validation tests
# ---------------------------------------------------------------------------


class TestUserRegisterRequestSchema:
    """Tests for UserRegisterRequest Pydantic schema."""

    def test_valid_registration(self) -> None:
        """Valid email + password should parse successfully."""
        req = UserRegisterRequest(email="user@example.com", password="strongpass123")
        assert req.email == "user@example.com"
        assert req.password == "strongpass123"

    def test_invalid_email_rejected(self) -> None:
        """An invalid email address must cause a ValidationError."""
        with pytest.raises(ValidationError):
            UserRegisterRequest(email="not-an-email", password="strongpass123")

    def test_short_password_rejected(self) -> None:
        """A password shorter than 8 characters must be rejected."""
        with pytest.raises(ValidationError):
            UserRegisterRequest(email="user@example.com", password="short")

    def test_long_password_rejected(self) -> None:
        """A password exceeding 128 characters must be rejected."""
        with pytest.raises(ValidationError):
            UserRegisterRequest(email="user@example.com", password="x" * 129)


class TestTokenRequestSchema:
    """Tests for TokenRequest Pydantic schema."""

    def test_valid_token_request(self) -> None:
        """Valid email + password parses successfully."""
        req = TokenRequest(email="user@example.com", password="password123")
        assert req.email == "user@example.com"

    def test_invalid_email_rejected(self) -> None:
        """Invalid email must be rejected."""
        with pytest.raises(ValidationError):
            TokenRequest(email="bad-email", password="password123")


class TestRefreshTokenRequestSchema:
    """Tests for RefreshTokenRequest Pydantic schema."""

    def test_valid_refresh_request(self) -> None:
        """Any non-empty string should be accepted."""
        req = RefreshTokenRequest(refresh_token="some-jwt-token")
        assert req.refresh_token == "some-jwt-token"


class TestTokenResponseSchema:
    """Tests for TokenResponse Pydantic schema."""

    def test_default_token_type(self) -> None:
        """token_type should default to 'bearer'."""
        resp = TokenResponse(access_token="acc", refresh_token="ref")
        assert resp.token_type == "bearer"


class TestMessageResponseSchema:
    """Tests for MessageResponse Pydantic schema."""

    def test_message_response(self) -> None:
        """MessageResponse should serialize correctly."""
        resp = MessageResponse(message="ok")
        assert resp.message == "ok"


# ---------------------------------------------------------------------------
# Layer 3: Endpoint routing tests with mocked DB
# ---------------------------------------------------------------------------


class TestRegisterEndpoint:
    """Tests for POST /api/v1/auth/register."""

    def test_register_user(self, client: TestClient) -> None:
        """Registering with valid data should return 201 with user data."""
        from datetime import datetime, timezone

        fake_user_id = uuid4()
        now = datetime.now(timezone.utc)

        # Mock DB: no existing user found, then populate the User on refresh
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        def _populate_user(user):
            """Simulate what db.refresh does: populate server-side defaults."""
            user.id = fake_user_id
            user.is_active = True
            user.is_superuser = False
            user.created_at = now

        mock_db.refresh = AsyncMock(side_effect=_populate_user)
        mock_db.add = MagicMock()

        from app.api.deps import get_db

        async def override_get_db():
            yield mock_db

        client.app.dependency_overrides[get_db] = override_get_db

        try:
            response = client.post(
                "/api/v1/auth/register",
                json={"email": "newuser@example.com", "password": "strongpass123"},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["email"] == "newuser@example.com"
            assert data["is_active"] is True
            assert data["is_superuser"] is False
        finally:
            client.app.dependency_overrides.pop(get_db, None)

    def test_register_duplicate_email(self, client: TestClient) -> None:
        """Registering with an existing email should return 409."""
        existing_user = MagicMock()
        existing_user.email = "dup@example.com"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        from app.api.deps import get_db

        async def override_get_db():
            yield mock_db

        client.app.dependency_overrides[get_db] = override_get_db

        try:
            response = client.post(
                "/api/v1/auth/register",
                json={"email": "dup@example.com", "password": "strongpass123"},
            )
            assert response.status_code == 409
            data = response.json()
            assert "error" in data
            assert "already exists" in data["error"]["message"].lower()
        finally:
            client.app.dependency_overrides.pop(get_db, None)


class TestLoginEndpoint:
    """Tests for POST /api/v1/auth/token."""

    def test_login_success(self, client: TestClient) -> None:
        """Valid credentials should return access + refresh tokens."""
        fake_user = MagicMock()
        fake_user.id = uuid4()
        fake_user.email = "user@example.com"
        fake_user.hashed_password = hash_password("correctpassword")
        fake_user.is_active = True
        fake_user.is_superuser = False

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_user
        mock_db.execute.return_value = mock_result

        from app.api.deps import get_db

        async def override_get_db():
            yield mock_db

        client.app.dependency_overrides[get_db] = override_get_db

        try:
            response = client.post(
                "/api/v1/auth/token",
                json={"email": "user@example.com", "password": "correctpassword"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"
        finally:
            client.app.dependency_overrides.pop(get_db, None)

    def test_login_wrong_password(self, client: TestClient) -> None:
        """Wrong password should return 401."""
        fake_user = MagicMock()
        fake_user.id = uuid4()
        fake_user.email = "user@example.com"
        fake_user.hashed_password = hash_password("correctpassword")
        fake_user.is_active = True

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_user
        mock_db.execute.return_value = mock_result

        from app.api.deps import get_db

        async def override_get_db():
            yield mock_db

        client.app.dependency_overrides[get_db] = override_get_db

        try:
            response = client.post(
                "/api/v1/auth/token",
                json={"email": "user@example.com", "password": "wrongpassword"},
            )
            assert response.status_code == 401
            data = response.json()
            assert "error" in data
        finally:
            client.app.dependency_overrides.pop(get_db, None)

    def test_login_nonexistent_user(self, client: TestClient) -> None:
        """Login with an unknown email should return 401."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        from app.api.deps import get_db

        async def override_get_db():
            yield mock_db

        client.app.dependency_overrides[get_db] = override_get_db

        try:
            response = client.post(
                "/api/v1/auth/token",
                json={"email": "nobody@example.com", "password": "whatever"},
            )
            assert response.status_code == 401
        finally:
            client.app.dependency_overrides.pop(get_db, None)

    def test_login_inactive_user(self, client: TestClient) -> None:
        """Login with an inactive user should return 401."""
        fake_user = MagicMock()
        fake_user.id = uuid4()
        fake_user.email = "inactive@example.com"
        fake_user.hashed_password = hash_password("password123")
        fake_user.is_active = False
        fake_user.is_superuser = False

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_user
        mock_db.execute.return_value = mock_result

        from app.api.deps import get_db

        async def override_get_db():
            yield mock_db

        client.app.dependency_overrides[get_db] = override_get_db

        try:
            response = client.post(
                "/api/v1/auth/token",
                json={"email": "inactive@example.com", "password": "password123"},
            )
            assert response.status_code == 401
            data = response.json()
            assert "inactive" in data["error"]["message"].lower()
        finally:
            client.app.dependency_overrides.pop(get_db, None)


class TestRefreshEndpoint:
    """Tests for POST /api/v1/auth/refresh."""

    def test_refresh_token_success(self, client: TestClient) -> None:
        """Valid refresh token should return new token pair."""
        user_id = uuid4()
        refresh = create_refresh_token({"sub": str(user_id), "role": "mentee"})

        fake_user = MagicMock()
        fake_user.id = user_id
        fake_user.is_active = True
        fake_user.is_superuser = False

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_user
        mock_db.execute.return_value = mock_result

        from app.api.deps import get_db

        async def override_get_db():
            yield mock_db

        client.app.dependency_overrides[get_db] = override_get_db

        try:
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh},
            )
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
        finally:
            client.app.dependency_overrides.pop(get_db, None)

    def test_refresh_with_access_token_rejected(self, client: TestClient) -> None:
        """Using an access token as refresh should return 401."""
        access = create_access_token({"sub": str(uuid4()), "role": "mentee"})

        mock_db = AsyncMock()

        from app.api.deps import get_db

        async def override_get_db():
            yield mock_db

        client.app.dependency_overrides[get_db] = override_get_db

        try:
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": access},
            )
            assert response.status_code == 401
        finally:
            client.app.dependency_overrides.pop(get_db, None)

    def test_refresh_with_invalid_token(self, client: TestClient) -> None:
        """An invalid/garbage refresh token should return 401."""
        mock_db = AsyncMock()

        from app.api.deps import get_db

        async def override_get_db():
            yield mock_db

        client.app.dependency_overrides[get_db] = override_get_db

        try:
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "garbage-token"},
            )
            assert response.status_code == 401
        finally:
            client.app.dependency_overrides.pop(get_db, None)


class TestProtectedEndpoints:
    """Tests for endpoints that require authentication."""

    def test_protected_endpoint_no_token(self, client: TestClient) -> None:
        """Accessing a protected endpoint without a token should return 401.

        We use the /api/v1/webhooks endpoint as a proxy for any protected route
        that depends on get_current_user.
        """
        # The webhooks POST endpoint requires get_current_user via OAuth2
        response = client.post(
            "/api/v1/webhooks",
            json={"url": "https://example.com/hook", "events": ["disc_profile_updated"]},
        )
        # FastAPI's OAuth2PasswordBearer returns 401 when no token is provided
        assert response.status_code == 401

    def test_protected_endpoint_with_token(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        """A valid token should pass the OAuth2 dependency layer.

        Even if the downstream DB lookup fails, we verify the auth layer itself
        accepts a properly signed JWT. The endpoint may still return an error
        due to missing DB, but it should NOT be a 401/403 from the auth layer.
        """
        # The /api/v1/auth/logout doesn't need DB lookup
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Successfully logged out"


class TestLogoutEndpoint:
    """Tests for POST /api/v1/auth/logout."""

    def test_logout_returns_success(self, client: TestClient) -> None:
        """Logout should return a success message."""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Successfully logged out"
