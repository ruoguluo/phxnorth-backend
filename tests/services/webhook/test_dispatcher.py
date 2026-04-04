"""Tests for webhook dispatcher: HMAC signing, verification, and dispatch."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.webhook.dispatcher import (
    dispatch_webhook,
    sign_payload,
    verify_signature,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SECRET = "test-webhook-secret-key"
PAYLOAD = {"event": "disc.profile.updated", "user_id": "user-123", "score": 72.5}
WEBHOOK_URL = "https://example.com/webhook"


# ---------------------------------------------------------------------------
# HMAC signing tests
# ---------------------------------------------------------------------------


class TestSignPayload:
    """Tests for sign_payload()."""

    def test_sign_payload(self) -> None:
        """sign_payload returns a sha256= prefixed HMAC-SHA256 hex digest."""
        signature = sign_payload(PAYLOAD, SECRET)

        assert signature.startswith("sha256=")
        hex_digest = signature[len("sha256="):]
        # Verify it's a valid hex string (64 chars for SHA-256)
        assert len(hex_digest) == 64
        int(hex_digest, 16)  # raises ValueError if not valid hex

    def test_sign_payload_deterministic(self) -> None:
        """Same payload and secret always produce the same signature."""
        sig1 = sign_payload(PAYLOAD, SECRET)
        sig2 = sign_payload(PAYLOAD, SECRET)
        assert sig1 == sig2

    def test_sign_payload_different_secrets(self) -> None:
        """Different secrets produce different signatures."""
        sig1 = sign_payload(PAYLOAD, "secret-a")
        sig2 = sign_payload(PAYLOAD, "secret-b")
        assert sig1 != sig2

    def test_sign_payload_different_payloads(self) -> None:
        """Different payloads produce different signatures."""
        sig1 = sign_payload({"a": 1}, SECRET)
        sig2 = sign_payload({"b": 2}, SECRET)
        assert sig1 != sig2

    def test_sign_payload_matches_manual_hmac(self) -> None:
        """Signature matches a manually computed HMAC-SHA256."""
        body = json.dumps(PAYLOAD, sort_keys=True, default=str)
        expected = hmac.new(
            SECRET.encode(), body.encode(), hashlib.sha256
        ).hexdigest()

        signature = sign_payload(PAYLOAD, SECRET)
        assert signature == f"sha256={expected}"


# ---------------------------------------------------------------------------
# Signature verification tests
# ---------------------------------------------------------------------------


class TestVerifySignature:
    """Tests for verify_signature()."""

    def test_verify_signature_valid(self) -> None:
        """Valid signature is accepted."""
        signature = sign_payload(PAYLOAD, SECRET)
        assert verify_signature(PAYLOAD, SECRET, signature) is True

    def test_verify_signature_invalid(self) -> None:
        """Tampered signature is rejected."""
        assert verify_signature(PAYLOAD, SECRET, "sha256=deadbeef" + "0" * 56) is False

    def test_verify_signature_wrong_secret(self) -> None:
        """Signature produced with different secret is rejected."""
        signature = sign_payload(PAYLOAD, "wrong-secret")
        assert verify_signature(PAYLOAD, SECRET, signature) is False

    def test_verify_signature_tampered_payload(self) -> None:
        """Signature doesn't match when payload is modified."""
        signature = sign_payload(PAYLOAD, SECRET)
        tampered = {**PAYLOAD, "score": 99.9}
        assert verify_signature(tampered, SECRET, signature) is False

    def test_verify_signature_empty_payload(self) -> None:
        """Empty payload can be signed and verified."""
        sig = sign_payload({}, SECRET)
        assert verify_signature({}, SECRET, sig) is True


# ---------------------------------------------------------------------------
# Webhook dispatch tests
# ---------------------------------------------------------------------------


class TestDispatchWebhook:
    """Tests for dispatch_webhook()."""

    @pytest.mark.asyncio
    async def test_dispatch_webhook_success(self) -> None:
        """Successful dispatch returns success=True with status code and timing."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.webhook.dispatcher.httpx.AsyncClient", return_value=mock_client):
            result = await dispatch_webhook(
                url=WEBHOOK_URL,
                payload=PAYLOAD,
                secret=SECRET,
                event_type="disc.profile.updated",
                delivery_id="test-delivery-001",
            )

        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["error"] is None
        assert result["delivery_id"] == "test-delivery-001"
        assert "duration_ms" in result
        assert isinstance(result["duration_ms"], float)

        # Verify the POST call was made with correct args
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs["json"] == PAYLOAD or call_kwargs[1]["json"] == PAYLOAD

    @pytest.mark.asyncio
    async def test_dispatch_webhook_failure(self) -> None:
        """Non-2xx response returns success=False with error description."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.webhook.dispatcher.httpx.AsyncClient", return_value=mock_client):
            result = await dispatch_webhook(
                url=WEBHOOK_URL,
                payload=PAYLOAD,
                secret=SECRET,
            )

        assert result["success"] is False
        assert result["status_code"] == 500
        assert result["error"] == "HTTP 500"
        assert "delivery_id" in result

    @pytest.mark.asyncio
    async def test_dispatch_webhook_timeout(self) -> None:
        """Timeout returns success=False with timeout error message."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.webhook.dispatcher.httpx.AsyncClient", return_value=mock_client):
            result = await dispatch_webhook(
                url=WEBHOOK_URL,
                payload=PAYLOAD,
                secret=SECRET,
                timeout=5,
            )

        assert result["success"] is False
        assert result["status_code"] is None
        assert "Timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_webhook_network_error(self) -> None:
        """Network error returns success=False with error description."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.webhook.dispatcher.httpx.AsyncClient", return_value=mock_client):
            result = await dispatch_webhook(
                url=WEBHOOK_URL,
                payload=PAYLOAD,
                secret=SECRET,
            )

        assert result["success"] is False
        assert result["status_code"] is None
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_dispatch_webhook_generates_delivery_id(self) -> None:
        """When no delivery_id is given, one is auto-generated."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.webhook.dispatcher.httpx.AsyncClient", return_value=mock_client):
            result = await dispatch_webhook(
                url=WEBHOOK_URL,
                payload=PAYLOAD,
                secret=SECRET,
            )

        assert result["delivery_id"] is not None
        assert len(result["delivery_id"]) > 0

    @pytest.mark.asyncio
    async def test_dispatch_webhook_sends_correct_headers(self) -> None:
        """Dispatch sends the expected signature, event type, and delivery headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.webhook.dispatcher.httpx.AsyncClient", return_value=mock_client):
            result = await dispatch_webhook(
                url=WEBHOOK_URL,
                payload=PAYLOAD,
                secret=SECRET,
                event_type="test.event",
                delivery_id="dlv-123",
            )

        # Extract the headers that were passed to client.post
        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")

        assert headers["X-PhxNorth-Event"] == "test.event"
        assert headers["X-PhxNorth-Delivery"] == "dlv-123"
        assert headers["Content-Type"] == "application/json"
        assert headers["X-PhxNorth-Signature"].startswith("sha256=")
