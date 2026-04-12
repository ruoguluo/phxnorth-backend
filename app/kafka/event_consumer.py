"""Kafka consumer that processes behavioral events through the signal extraction
and DISC scoring pipeline."""

import logging
from typing import Any

from app.cache.disc_cache import DISCProfileCache
from app.cache.redis_client import RedisCacheService
from app.kafka.consumer import KafkaConsumerService
from app.kafka.topics import KafkaTopic
from app.services.signal_extractor.worker import process_behavioral_events
from app.services.disc_scorer.worker import compute_user_disc_profile
from app.services.disc_scorer.scorer import WeightedSignal

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "behavioral-events-processor"


async def _handle_event(message: dict[str, Any]) -> None:
    """Process a single behavioral event message from Kafka."""
    user_id = message.get("user_id")
    event_type = message.get("event_type", "unknown")

    if not user_id:
        logger.warning("Skipping event with no user_id: %s", message.get("event_id"))
        return

    logger.info("Processing event %s for user %s (type: %s)",
                message.get("event_id", "?"), user_id, event_type)

    try:
        events_list = [message]
        extraction_result = await process_behavioral_events(
            events=events_list,
            user_id=user_id,
            window_days=90,
        )

        if not extraction_result.get("success"):
            logger.warning("Signal extraction failed for user %s: %s",
                           user_id, extraction_result.get("error"))
            return

        signals = extraction_result.get("signals", [])
        if not signals:
            logger.debug("No signals extracted from event %s for user %s",
                         event_type, user_id)
            return

        weighted_signals = []
        for sig in signals:
            weighted_signals.append(WeightedSignal(
                signal_type=sig.get("signal_type", event_type),
                confidence=sig.get("confidence", 0.5),
                source=sig.get("source", "platform"),
                timestamp=sig.get("timestamp"),
            ))

        if not weighted_signals:
            return

        score_result = await compute_user_disc_profile(
            signals=weighted_signals,
            user_id=user_id,
        )

        if not score_result.get("success"):
            logger.warning("DISC scoring failed for user %s: %s",
                           user_id, score_result.get("error"))
            return

        logger.info("Updated DISC profile for user %s: dominant=%s confidence=%.2f (%d signals)",
                     user_id,
                     score_result.get("dominant", "?"),
                     score_result.get("confidence", 0),
                     score_result.get("signal_count", 0))

    except Exception as e:
        logger.exception("Error processing event for user %s: %s", user_id, e)


async def _invalidate_user_cache(user_id: str, redis: RedisCacheService | None) -> None:
    if redis is None:
        return
    try:
        cache = DISCProfileCache(redis)
        await cache.invalidate(user_id)
        logger.debug("Invalidated DISC cache for user %s", user_id)
    except Exception as e:
        logger.warning("Cache invalidation failed for user %s: %s", user_id, e)


async def _handle_event_with_cache(message: dict[str, Any], redis: RedisCacheService | None) -> None:
    await _handle_event(message)
    user_id = message.get("user_id")
    if user_id:
        await _invalidate_user_cache(user_id, redis)


def create_event_consumer(redis: RedisCacheService | None = None) -> KafkaConsumerService:
    async def handler(message: dict[str, Any]) -> None:
        await _handle_event_with_cache(message, redis)

    return KafkaConsumerService(
        topic=KafkaTopic.RAW_BEHAVIORAL_EVENTS.value,
        group_id=CONSUMER_GROUP,
        handler=handler,
    )
