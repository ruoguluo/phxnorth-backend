"""Event deduplication via Redis.

Provides an atomic check-and-mark mechanism so that each event is
processed **exactly once** within the deduplication window.
"""

from __future__ import annotations

import structlog

from app.cache.redis_client import RedisCacheService

logger = structlog.get_logger(__name__)

# Default dedup window: 60 seconds
_DEFAULT_TTL = 60


class EventDeduplicator:
    """Guard against duplicate event processing.

    Key pattern (prefix ``phxnorth:`` added automatically)::

        dedup:event:{event_id}   → "1"  (TTL 60 s by default)
    """

    def __init__(self, redis: RedisCacheService) -> None:
        self._redis = redis

    def _key(self, event_id: str) -> str:
        return f"dedup:event:{event_id}"

    async def is_duplicate(self, event_id: str) -> bool:
        """Return ``True`` if *event_id* was already processed."""
        return await self._redis.exists(self._key(event_id))

    async def mark_processed(
        self, event_id: str, ttl: int = _DEFAULT_TTL
    ) -> None:
        """Mark *event_id* as processed with a TTL."""
        await self._redis.set(self._key(event_id), "1", ttl_seconds=ttl)
        logger.debug("event_marked_processed", event_id=event_id, ttl=ttl)

    async def check_and_mark(
        self, event_id: str, ttl: int = _DEFAULT_TTL
    ) -> bool:
        """Atomic check-and-mark using ``SET NX EX``.

        Returns ``True`` if the event is **new** (not a duplicate) and has
        been marked as processed in one atomic step.  Returns ``False`` if
        the event was already processed (duplicate).
        """
        is_new = await self._redis.set_if_not_exists(
            self._key(event_id), "1", ttl_seconds=ttl
        )
        if is_new:
            logger.debug("event_new", event_id=event_id, ttl=ttl)
        else:
            logger.debug("event_duplicate", event_id=event_id)
        return is_new
