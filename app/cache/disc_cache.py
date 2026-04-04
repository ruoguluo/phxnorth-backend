"""DISC profile caching layer built on RedisCacheService.

Caches computed DISC profiles per user and time window with 1-hour TTL.
Supports cache-aside reads, bulk writes, and per-user invalidation.

Key schema::

    phxnorth:disc:{user_id}:30d       → DISCScores JSON (TTL 1 hr)
    phxnorth:disc:{user_id}:90d       → DISCScores JSON (TTL 1 hr)
    phxnorth:disc:{user_id}:lifetime  → DISCScores JSON (TTL 1 hr)
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import structlog

from app.cache.redis_client import RedisCacheService

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TTL_SECONDS: int = 3600  # 1 hour
"""Default TTL for cached DISC profiles."""

VALID_WINDOWS: frozenset[str] = frozenset({"30d", "90d", "lifetime"})
"""Allowed window labels.  Used for key construction and validation."""


def _disc_key(user_id: str, window: str) -> str:
    """Build the Redis key for a user's DISC profile at a given window.

    The ``phxnorth:`` prefix is added automatically by
    :class:`~app.cache.redis_client.RedisCacheService`, so we only need
    the domain-specific portion here.
    """
    return f"disc:{user_id}:{window}"


# ---------------------------------------------------------------------------
# Cache class
# ---------------------------------------------------------------------------


class DISCProfileCache:
    """Cache layer for DISC profiles.

    All methods are thin wrappers around :class:`RedisCacheService` JSON
    helpers, adding domain-specific key construction and logging.

    Parameters:
        redis: An already-connected :class:`RedisCacheService` instance.
    """

    def __init__(self, redis: RedisCacheService) -> None:
        self.redis = redis

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_profile(
        self,
        user_id: str,
        window: str = "90d",
    ) -> dict[str, Any] | None:
        """Get a cached DISC profile.

        Args:
            user_id: The user whose profile to retrieve.
            window: Time window label (``"30d"``, ``"90d"``, or
                ``"lifetime"``).

        Returns:
            The cached profile dict, or ``None`` on miss.
        """
        key = _disc_key(user_id, window)
        data = await self.redis.get_json(key)
        if data is not None:
            logger.debug("disc_cache_hit", user_id=user_id, window=window)
        else:
            logger.debug("disc_cache_miss", user_id=user_id, window=window)
        return data

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def set_profile(
        self,
        user_id: str,
        window: str,
        profile: dict[str, Any],
        ttl: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        """Cache a single DISC profile.

        Args:
            user_id: The user whose profile to cache.
            window: Time window label.
            profile: Serialised DISC scores dict.
            ttl: Time-to-live in seconds (default 1 hour).
        """
        key = _disc_key(user_id, window)
        await self.redis.set_json(key, profile, ttl_seconds=ttl)
        logger.debug(
            "disc_cache_set",
            user_id=user_id,
            window=window,
            ttl=ttl,
        )

    async def set_all_windows(
        self,
        user_id: str,
        profiles: dict[str, dict[str, Any]],
        ttl: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        """Cache all 3 windowed profiles at once.

        This is a convenience wrapper that sets ``30d``, ``90d``, and
        ``lifetime`` entries in a single logical operation.  If *profiles*
        contains extra keys they are silently ignored; missing windows are
        skipped.

        Args:
            user_id: The user whose profiles to cache.
            profiles: Mapping of window label → DISC scores dict.
            ttl: Time-to-live in seconds (default 1 hour).
        """
        for window in VALID_WINDOWS:
            profile = profiles.get(window)
            if profile is not None:
                await self.set_profile(user_id, window, profile, ttl=ttl)

        logger.debug(
            "disc_cache_set_all",
            user_id=user_id,
            windows=sorted(profiles.keys() & VALID_WINDOWS),
            ttl=ttl,
        )

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    async def invalidate(self, user_id: str) -> None:
        """Invalidate all cached profiles for a user.

        Uses a pattern scan to delete every key matching
        ``phxnorth:disc:{user_id}:*``.
        """
        pattern = f"disc:{user_id}:*"
        deleted = await self.redis.delete_pattern(pattern)
        logger.info(
            "disc_cache_invalidated",
            user_id=user_id,
            keys_deleted=deleted,
        )

    # ------------------------------------------------------------------
    # Cache-aside
    # ------------------------------------------------------------------

    async def get_or_compute(
        self,
        user_id: str,
        window: str,
        compute_fn: Callable[[], Awaitable[dict[str, Any]]],
        ttl: int = DEFAULT_TTL_SECONDS,
    ) -> dict[str, Any]:
        """Get from cache or compute and cache (cache-aside pattern).

        If the profile is not in the cache, *compute_fn* is awaited to
        produce it.  The result is then cached before being returned.

        Args:
            user_id: The user whose profile to retrieve or compute.
            window: Time window label.
            compute_fn: An async callable that produces the profile dict
                when the cache misses.  It receives no arguments — the
                caller is expected to bind any required state via a
                closure or ``functools.partial``.
            ttl: Time-to-live in seconds (default 1 hour).

        Returns:
            The DISC profile dict (from cache or freshly computed).
        """
        cached = await self.get_profile(user_id, window)
        if cached is not None:
            return cached

        profile = await compute_fn()
        await self.set_profile(user_id, window, profile, ttl=ttl)
        logger.debug(
            "disc_cache_computed",
            user_id=user_id,
            window=window,
        )
        return profile
