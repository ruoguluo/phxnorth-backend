"""Dead letter queue (DLQ) handler for failed Kafka messages.

Messages that exhaust all retry attempts are routed to a DLQ topic
(convention: ``{original_topic}.dlq``) so they can be inspected,
replayed, or alerted on without blocking the main consumer pipeline.

DLQ topics:
    - raw.cv.uploads.dlq
    - raw.behavioral.events.dlq
    - signals.cv.dlq
    - signals.platform.dlq
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DLQ_SUFFIX = ".dlq"


class KafkaProducerProtocol(Protocol):
    """Minimal interface required from the Kafka producer."""

    async def send(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
    ) -> None: ...


class DeadLetterQueue:
    """Routes failed messages to dead letter queue topics.

    After a consumer exhausts its retry budget the original message,
    together with error metadata, is published to the corresponding
    DLQ topic so operators can triage failures without losing data.
    """

    def __init__(self, producer: KafkaProducerProtocol) -> None:
        self._producer = producer

    async def send_to_dlq(
        self,
        original_topic: str,
        message: dict[str, Any],
        error: str,
        retry_count: int,
        original_key: str | None = None,
    ) -> None:
        """Send a failed message to the DLQ topic.

        Wraps the original message with error metadata and publishes it
        to ``{original_topic}.dlq``.

        Args:
            original_topic: The topic the message was originally consumed from.
            message: The original message payload that failed processing.
            error: Human-readable description of the failure.
            retry_count: Number of processing attempts before giving up.
            original_key: The Kafka key of the original message, if any.
        """
        dlq_topic = self.get_dlq_topic(original_topic)

        dlq_message: dict[str, Any] = {
            "original_topic": original_topic,
            "original_message": message,
            "error": error,
            "retry_count": retry_count,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "original_key": original_key,
        }

        try:
            await self._producer.send(
                topic=dlq_topic,
                value=dlq_message,
                key=original_key,
            )
            logger.warning(
                "message_sent_to_dlq",
                original_topic=original_topic,
                dlq_topic=dlq_topic,
                error=error,
                retry_count=retry_count,
                original_key=original_key,
            )
        except Exception:
            # If we can't even reach the DLQ we must not swallow the
            # error — log at critical so alerting picks it up.
            logger.critical(
                "dlq_send_failed",
                original_topic=original_topic,
                dlq_topic=dlq_topic,
                error=error,
                retry_count=retry_count,
                original_key=original_key,
                exc_info=True,
            )
            raise

    @staticmethod
    def get_dlq_topic(original_topic: str) -> str:
        """Get DLQ topic name for an original topic.

        Args:
            original_topic: The source topic name.

        Returns:
            The corresponding DLQ topic name (``{original_topic}.dlq``).
        """
        return f"{original_topic}{DLQ_SUFFIX}"
