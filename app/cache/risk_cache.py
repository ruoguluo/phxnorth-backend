"""Caching layer for risk assessments and user preference indexes."""

from __future__ import annotations

from typing import Any

import structlog

from app.cache.redis_client import RedisCacheService

logger = structlog.get_logger(__name__)

# Default TTL: 1 hour
_DEFAULT_TTL = 3600


class RiskCache:
    """Read-through cache for risk assessments and preference indexes.

    Key patterns (prefix ``phxnorth:`` is added automatically by the
    underlying :class:`RedisCacheService`)::

        risk:{user_id}:latest    → risk assessment JSON
        prefs:{user_id}:latest   → PreferenceIndexes JSON
    """

    def __init__(self, redis: RedisCacheService) -> None:
        self._redis = redis

    # ------------------------------------------------------------------
    # Risk assessments
    # ------------------------------------------------------------------

    async def get_risk(self, user_id: str) -> dict[str, Any] | None:
        """Return the cached risk assessment for *user_id*, or ``None``."""
        data = await self._redis.get_json(f"risk:{user_id}:latest")
        if data is not None:
            logger.debug("risk_cache_hit", user_id=user_id)
        else:
            logger.debug("risk_cache_miss", user_id=user_id)
        return data

    async def set_risk(
        self,
        user_id: str,
        risk_data: dict[str, Any],
        ttl: int = _DEFAULT_TTL,
    ) -> None:
        """Store a risk assessment for *user_id* with a TTL (default 1 hr)."""
        await self._redis.set_json(
            f"risk:{user_id}:latest", risk_data, ttl_seconds=ttl
        )
        logger.debug("risk_cache_set", user_id=user_id, ttl=ttl)

    # ------------------------------------------------------------------
    # Preference indexes
    # ------------------------------------------------------------------

    async def get_preferences(self, user_id: str) -> dict[str, Any] | None:
        """Return cached preference indexes for *user_id*, or ``None``."""
        data = await self._redis.get_json(f"prefs:{user_id}:latest")
        if data is not None:
            logger.debug("prefs_cache_hit", user_id=user_id)
        else:
            logger.debug("prefs_cache_miss", user_id=user_id)
        return data

    async def set_preferences(
        self,
        user_id: str,
        prefs: dict[str, Any],
        ttl: int = _DEFAULT_TTL,
    ) -> None:
        """Store preference indexes for *user_id* with a TTL (default 1 hr)."""
        await self._redis.set_json(
            f"prefs:{user_id}:latest", prefs, ttl_seconds=ttl
        )
        logger.debug("prefs_cache_set", user_id=user_id, ttl=ttl)

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    async def invalidate_user(self, user_id: str) -> None:
        """Remove **all** cached risk and preference data for *user_id*.

        Uses pattern-based deletion so any future qualifier variants
        (e.g. ``risk:{user_id}:v2``) are also cleared.
        """
        risk_deleted = await self._redis.delete_pattern(f"risk:{user_id}:*")
        prefs_deleted = await self._redis.delete_pattern(f"prefs:{user_id}:*")
        logger.info(
            "user_cache_invalidated",
            user_id=user_id,
            risk_keys=risk_deleted,
            prefs_keys=prefs_deleted,
        )
