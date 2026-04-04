"""Async Kafka consumer base class with error handling.

Provides a reusable consumer service that deserializes JSON messages and
delegates processing to a caller-supplied handler coroutine.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any

import structlog
from aiokafka import AIOKafkaConsumer
from aiokafka.structs import ConsumerRecord

from app.config import get_settings

logger = structlog.get_logger(__name__)

# Type alias for the async message handler signature.
MessageHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


def _json_deserializer(raw: bytes) -> dict[str, Any]:
    """Deserialize UTF-8 JSON bytes to a dict."""
    return json.loads(raw.decode("utf-8"))


class KafkaConsumerService:
    """Async Kafka consumer base class with error handling.

    The consumer subscribes to a single topic inside a consumer group and
    delegates each deserialized message to the provided *handler* coroutine.

    Usage::

        async def handle_event(message: dict) -> None:
            print(message)

        consumer = KafkaConsumerService(
            topic="raw.behavioral.events",
            group_id="signal-extractor",
            handler=handle_event,
        )
        await consumer.start()
        # consumer runs in the background until stop() is called
        await consumer.stop()
    """

    def __init__(
        self,
        topic: str,
        group_id: str,
        handler: MessageHandler,
        *,
        max_retries: int = 3,
    ) -> None:
        """Initialize the consumer.

        Args:
            topic: Kafka topic to subscribe to.
            group_id: Consumer group ID for offset management.
            handler: Async callable invoked with each deserialized message dict.
            max_retries: Maximum number of processing retries per message
                before the message is logged and skipped.
        """
        settings = get_settings()
        self._bootstrap_servers = settings.kafka_bootstrap_servers
        self._topic = topic
        self._group_id = group_id
        self._handler = handler
        self._max_retries = max_retries
        self._consumer: AIOKafkaConsumer | None = None
        self._consume_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the consumer and begin processing messages in the background.

        Raises:
            RuntimeError: If the consumer is already started.
        """
        if self._consumer is not None:
            raise RuntimeError("KafkaConsumerService is already started")

        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._group_id,
            value_deserializer=_json_deserializer,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            auto_commit_interval_ms=5_000,
            session_timeout_ms=30_000,
        )
        await self._consumer.start()
        self._consume_task = asyncio.create_task(
            self._consume_loop(),
            name=f"kafka-consumer-{self._topic}-{self._group_id}",
        )
        logger.info(
            "kafka_consumer_started",
            topic=self._topic,
            group_id=self._group_id,
            bootstrap_servers=self._bootstrap_servers,
        )

    async def stop(self) -> None:
        """Stop the consumer gracefully, cancelling the background loop."""
        if self._consume_task is not None:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
            self._consume_task = None

        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
            logger.info(
                "kafka_consumer_stopped",
                topic=self._topic,
                group_id=self._group_id,
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _consume_loop(self) -> None:
        """Poll for messages and dispatch them to the handler."""
        assert self._consumer is not None  # noqa: S101
        try:
            async for message in self._consumer:
                await self._process_message(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "kafka_consume_loop_error",
                topic=self._topic,
                group_id=self._group_id,
            )
            raise

    async def _process_message(self, message: ConsumerRecord) -> None:
        """Deserialize and hand off a single message to the handler.

        Retries up to ``max_retries`` times on handler failure. If all
        retries are exhausted the message is logged and skipped so the
        consumer does not stall.

        Args:
            message: The raw Kafka ``ConsumerRecord``.
        """
        log = logger.bind(
            topic=message.topic,
            partition=message.partition,
            offset=message.offset,
            key=message.key.decode("utf-8") if message.key else None,
        )

        for attempt in range(1, self._max_retries + 1):
            try:
                await self._handler(message.value)
                log.debug("kafka_message_processed", attempt=attempt)
                return
            except Exception:
                log.warning(
                    "kafka_message_handler_error",
                    attempt=attempt,
                    max_retries=self._max_retries,
                    exc_info=True,
                )
                if attempt < self._max_retries:
                    # Exponential back-off: 0.5s, 1s, 2s …
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        # All retries exhausted — skip the message
        log.error(
            "kafka_message_skipped",
            reason="max_retries_exhausted",
            max_retries=self._max_retries,
            message_value=message.value,
        )
