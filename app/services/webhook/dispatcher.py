"""Webhook dispatcher with HMAC-SHA256 signing, delivery tracking, and retry.

Each outgoing webhook POST carries four headers:

    X-PhxNorth-Signature  – sha256={hmac_hex}
    Content-Type          – application/json
    X-PhxNorth-Event      – event type string
    X-PhxNorth-Delivery   – unique delivery UUID

The :func:`dispatch_webhook` function sends a single attempt while
:func:`dispatch_webhook_with_retry` wraps it with exponential back-off.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry defaults
# ---------------------------------------------------------------------------

DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0  # seconds
DEFAULT_RETRY_MAX_DELAY = 30.0  # seconds
DEFAULT_RETRY_BACKOFF_FACTOR = 2.0

# HTTP status codes worth retrying on
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


# ---------------------------------------------------------------------------
# HMAC signing / verification
# ---------------------------------------------------------------------------


def sign_payload(payload: dict, secret: str) -> str:
    """Create HMAC-SHA256 signature for a webhook payload.

    The payload is serialised with sorted keys and ``default=str`` to ensure
    deterministic output.

    Returns:
        String of the form ``"sha256={hex_digest}"``.
    """
    body = json.dumps(payload, sort_keys=True, default=str)
    digest = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(payload: dict, secret: str, signature: str) -> bool:
    """Verify an HMAC-SHA256 signature against a payload and secret.

    Uses :func:`hmac.compare_digest` for constant-time comparison to avoid
    timing attacks.
    """
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Single dispatch
# ---------------------------------------------------------------------------


async def dispatch_webhook(
    url: str,
    payload: dict,
    secret: str,
    *,
    event_type: str = "ping",
    delivery_id: str | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    """Send a single webhook POST with HMAC signature.

    Parameters
    ----------
    url:
        Target endpoint URL.
    payload:
        JSON-serialisable dict sent as the request body.
    secret:
        Shared secret used for HMAC-SHA256 signing.
    event_type:
        Value for the ``X-PhxNorth-Event`` header.
    delivery_id:
        Unique delivery identifier.  A UUID is generated when *None*.
    timeout:
        HTTP request timeout in seconds.

    Returns
    -------
    dict
        ``success`` – whether the request completed with a 2xx status.
        ``status_code`` – HTTP status code or *None* on transport error.
        ``error`` – error description or *None*.
        ``duration_ms`` – round-trip time in milliseconds.
        ``delivery_id`` – the delivery UUID used for this attempt.
    """
    if delivery_id is None:
        delivery_id = str(uuid.uuid4())

    signature = sign_payload(payload, secret)
    headers = {
        "X-PhxNorth-Signature": signature,
        "Content-Type": "application/json",
        "X-PhxNorth-Event": event_type,
        "X-PhxNorth-Delivery": delivery_id,
    }

    start = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
        duration_ms = (time.monotonic() - start) * 1000

        success = 200 <= response.status_code < 300
        if not success:
            logger.warning(
                "Webhook delivery %s to %s returned %d",
                delivery_id,
                url,
                response.status_code,
            )

        return {
            "success": success,
            "status_code": response.status_code,
            "error": None if success else f"HTTP {response.status_code}",
            "duration_ms": round(duration_ms, 2),
            "delivery_id": delivery_id,
        }

    except httpx.TimeoutException:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error(
            "Webhook delivery %s to %s timed out after %ds",
            delivery_id,
            url,
            timeout,
        )
        return {
            "success": False,
            "status_code": None,
            "error": f"Timeout after {timeout}s",
            "duration_ms": round(duration_ms, 2),
            "delivery_id": delivery_id,
        }

    except httpx.HTTPError as exc:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error(
            "Webhook delivery %s to %s failed: %s",
            delivery_id,
            url,
            exc,
        )
        return {
            "success": False,
            "status_code": None,
            "error": str(exc),
            "duration_ms": round(duration_ms, 2),
            "delivery_id": delivery_id,
        }


# ---------------------------------------------------------------------------
# Dispatch with retry
# ---------------------------------------------------------------------------


async def dispatch_webhook_with_retry(
    url: str,
    payload: dict,
    secret: str,
    *,
    event_type: str = "ping",
    delivery_id: str | None = None,
    timeout: int = 10,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    retry_max_delay: float = DEFAULT_RETRY_MAX_DELAY,
    retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR,
) -> dict[str, Any]:
    """Dispatch a webhook with exponential back-off retry.

    The function retries on network errors and on specific HTTP status codes
    (408, 429, 500, 502, 503, 504).  Each retry uses the *same* delivery ID so
    receivers can deduplicate.

    Returns the result dict from the last attempt, augmented with:

    * ``attempts`` – total number of attempts made.
    * ``delivery_id`` – the stable delivery UUID across all attempts.
    """
    import asyncio

    if delivery_id is None:
        delivery_id = str(uuid.uuid4())

    last_result: dict[str, Any] = {}

    for attempt in range(1, max_retries + 1):
        result = await dispatch_webhook(
            url,
            payload,
            secret,
            event_type=event_type,
            delivery_id=delivery_id,
            timeout=timeout,
        )
        last_result = result

        if result["success"]:
            last_result["attempts"] = attempt
            return last_result

        # Decide whether to retry
        status = result.get("status_code")
        is_retryable = status is None or status in RETRYABLE_STATUS_CODES

        if not is_retryable:
            logger.info(
                "Webhook %s: non-retryable status %s on attempt %d/%d",
                delivery_id,
                status,
                attempt,
                max_retries,
            )
            last_result["attempts"] = attempt
            return last_result

        if attempt < max_retries:
            delay = min(
                retry_base_delay * (retry_backoff_factor ** (attempt - 1)),
                retry_max_delay,
            )
            logger.info(
                "Webhook %s: attempt %d/%d failed, retrying in %.1fs",
                delivery_id,
                attempt,
                max_retries,
                delay,
            )
            await asyncio.sleep(delay)

    last_result["attempts"] = max_retries
    logger.error(
        "Webhook %s: exhausted %d retries for %s",
        delivery_id,
        max_retries,
        url,
    )
    return last_result
