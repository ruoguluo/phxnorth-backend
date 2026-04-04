"""Async Redis cache service with connection management and JSON helpers."""

from __future__ import annotations

import json
from typing import Any

import structlog
from redis.asyncio import Redis

from app.config import get_settings

logger = structlog.get_logger(__name__)

CACHE_PREFIX = "phxnorth"


def _prefixed(key: str) -> str:
    """Ensure the key carries the global prefix.

    Keys that already start with the prefix are returned unchanged so callers
    can safely pass either raw or pre-prefixed keys.
    """
    if key.startswith(f"{CACHE_PREFIX}:"):
        return key
    return f"{CACHE_PREFIX}:{key}"


class RedisCacheService:
    """Async Redis cache service.

    Wraps ``redis.asyncio.Redis`` with:
    * automatic key prefixing (``phxnorth:{domain}:{id}:{qualifier}``)
    * JSON get/set helpers
    * pattern-based key deletion
    * clean connect / disconnect lifecycle hooks
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or get_settings().redis_url
        self._redis: Redis | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the connection pool."""
        if self._redis is not None:
            return
        self._redis = Redis.from_url(
            self._redis_url,
            decode_responses=True,
        )
        # Verify connectivity
        try:
            await self._redis.ping()
            logger.info("redis_connected", url=self._redis_url)
        except Exception:
            logger.error("redis_connection_failed", url=self._redis_url)
            raise

    async def disconnect(self) -> None:
        """Close the connection pool gracefully."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            logger.info("redis_disconnected")

    @property
    def client(self) -> Redis:
        """Return the underlying Redis client, raising if not connected."""
        if self._redis is None:
            raise RuntimeError(
                "RedisCacheService is not connected. Call connect() first."
            )
        return self._redis

    # ------------------------------------------------------------------
    # Basic get / set / delete
    # ------------------------------------------------------------------

    async def get(self, key: str) -> str | None:
        """Get a string value by key."""
        return await self.client.get(_prefixed(key))

    async def set(
        self, key: str, value: str, ttl_seconds: int | None = None
    ) -> None:
        """Set a string value, optionally with a TTL."""
        prefixed = _prefixed(key)
        if ttl_seconds is not None:
            await self.client.setex(prefixed, ttl_seconds, value)
        else:
            await self.client.set(prefixed, value)

    async def delete(self, key: str) -> None:
        """Delete a single key."""
        await self.client.delete(_prefixed(key))

    async def exists(self, key: str) -> bool:
        """Check whether a key exists."""
        return bool(await self.client.exists(_prefixed(key)))

    # ------------------------------------------------------------------
    # JSON helpers
    # ------------------------------------------------------------------

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Get a value and deserialise it from JSON."""
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)  # type: ignore[no-any-return]
        except (json.JSONDecodeError, TypeError):
            logger.warning("redis_json_decode_error", key=key)
            return None

    async def set_json(
        self,
        key: str,
        value: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        """Serialise *value* as JSON and store it."""
        await self.set(key, json.dumps(value, default=str), ttl_seconds)

    # ------------------------------------------------------------------
    # Atomic helpers
    # ------------------------------------------------------------------

    async def set_if_not_exists(
        self, key: str, value: str, ttl_seconds: int
    ) -> bool:
        """Set a key only if it does not already exist (NX + EX).

        Useful for distributed locks and idempotency guards.
        Returns ``True`` when the key was set, ``False`` if it already existed.
        """
        result = await self.client.set(
            _prefixed(key), value, ex=ttl_seconds, nx=True
        )
        return result is not None and bool(result)

    # ------------------------------------------------------------------
    # Pattern operations
    # ------------------------------------------------------------------

    async def get_keys(self, pattern: str) -> list[str]:
        """Return all keys matching *pattern* (automatically prefixed).

        Uses ``SCAN`` under the hood to avoid blocking the server.
        """
        prefixed_pattern = _prefixed(pattern)
        keys: list[str] = []
        async for key in self.client.scan_iter(match=prefixed_pattern):
            keys.append(key)
        return keys

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching *pattern* and return the count deleted.

        Uses ``SCAN`` + ``UNLINK`` in batches to avoid blocking.
        """
        prefixed_pattern = _prefixed(pattern)
        deleted = 0
        batch: list[str] = []
        async for key in self.client.scan_iter(match=prefixed_pattern):
            batch.append(key)
            if len(batch) >= 500:
                deleted += await self.client.unlink(*batch)
                batch = []
        if batch:
            deleted += await self.client.unlink(*batch)
        return deleted
