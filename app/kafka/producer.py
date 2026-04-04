"""Async Kafka producer with JSON serialization.

Provides a reusable producer service that serializes messages as JSON
and supports keyed messages for consistent partition routing (e.g. by user_id).
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from aiokafka import AIOKafkaProducer

from app.config import get_settings

logger = structlog.get_logger(__name__)


def _json_serializer(value: dict[str, Any]) -> bytes:
    """Serialize a dict to UTF-8 JSON bytes."""
    return json.dumps(value, default=str).encode("utf-8")


def _key_serializer(key: str) -> bytes:
    """Serialize a message key to UTF-8 bytes."""
    return key.encode("utf-8")


class KafkaProducerService:
    """Async Kafka producer with JSON serialization.

    Usage::

        producer = KafkaProducerService()
        await producer.start()
        try:
            await producer.send("raw.behavioral.events", {"user_id": "abc", ...})
        finally:
            await producer.stop()

    The producer can also be used in the FastAPI lifespan context to manage
    its lifecycle alongside the application.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._bootstrap_servers = settings.kafka_bootstrap_servers
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        """Start the Kafka producer and wait for it to be ready.

        Raises:
            RuntimeError: If the producer is already started.
        """
        if self._producer is not None:
            raise RuntimeError("KafkaProducerService is already started")

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            value_serializer=_json_serializer,
            key_serializer=_key_serializer,
            # Ensure at-least-once delivery
            acks="all",
            # Retry transient errors
            retry_backoff_ms=100,
            request_timeout_ms=30_000,
        )
        await self._producer.start()
        logger.info(
            "kafka_producer_started",
            bootstrap_servers=self._bootstrap_servers,
        )

    async def stop(self) -> None:
        """Flush pending messages and stop the producer gracefully."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            logger.info("kafka_producer_stopped")

    async def send(
        self,
        topic: str,
        message: dict[str, Any],
        key: str | None = None,
    ) -> None:
        """Send a single message to a Kafka topic.

        Args:
            topic: Destination topic name.
            message: Dict payload to be JSON-serialized.
            key: Optional partition key (e.g. user_id) for consistent
                partition routing.

        Raises:
            RuntimeError: If the producer has not been started.
        """
        if self._producer is None:
            raise RuntimeError(
                "KafkaProducerService is not started. Call start() first."
            )

        try:
            await self._producer.send_and_wait(
                topic,
                value=message,
                key=key,
            )
            logger.debug(
                "kafka_message_sent",
                topic=topic,
                key=key,
            )
        except Exception:
            logger.exception(
                "kafka_send_failed",
                topic=topic,
                key=key,
            )
            raise

    async def send_batch(
        self,
        topic: str,
        messages: list[dict[str, Any]],
        key: str | None = None,
    ) -> None:
        """Send a batch of messages to a Kafka topic.

        Messages are sent concurrently via the internal buffer and then
        flushed together, which is more efficient than individual
        ``send_and_wait`` calls for bulk workloads.

        Args:
            topic: Destination topic name.
            messages: List of dict payloads to be JSON-serialized.
            key: Optional partition key applied to all messages in the batch.

        Raises:
            RuntimeError: If the producer has not been started.
        """
        if self._producer is None:
            raise RuntimeError(
                "KafkaProducerService is not started. Call start() first."
            )

        if not messages:
            return

        try:
            # Queue all messages into the producer buffer
            futures = [
                await self._producer.send(topic, value=msg, key=key)
                for msg in messages
            ]
            # Wait for all to be acknowledged
            for fut in futures:
                await fut
            logger.info(
                "kafka_batch_sent",
                topic=topic,
                count=len(messages),
                key=key,
            )
        except Exception:
            logger.exception(
                "kafka_batch_send_failed",
                topic=topic,
                count=len(messages),
                key=key,
            )
            raise
