"""Kafka topic definitions and configuration for the PhxNorth event pipeline.

Each topic is defined with its partition count, retention period, and description.
These configurations are used by the topic admin client to create/validate topics
on startup.
"""

import enum
from dataclasses import dataclass


class KafkaTopic(str, enum.Enum):
    """Kafka topic names used throughout the pipeline."""

    # Ingestion layer
    RAW_CV_UPLOADS = "raw.cv.uploads"
    RAW_BEHAVIORAL_EVENTS = "raw.behavioral.events"

    # Signal extraction layer
    SIGNALS_CV = "signals.cv"
    SIGNALS_PLATFORM = "signals.platform"

    # DISC scoring layer
    DISC_SCORE_UPDATES = "disc.score.updates"

    # Risk assessment layer
    RISK_FLAG_EVENTS = "risk.flag.events"


@dataclass(frozen=True)
class TopicConfig:
    """Configuration for a Kafka topic.

    Attributes:
        topic: The KafkaTopic enum value.
        partitions: Number of partitions for the topic.
        retention_ms: Message retention period in milliseconds.
        description: Human-readable description of the topic's purpose.
        replication_factor: Number of replicas (default 1 for dev, override in prod).
    """

    topic: KafkaTopic
    partitions: int
    retention_ms: int
    description: str
    replication_factor: int = 1

    @property
    def name(self) -> str:
        """Return the string topic name."""
        return self.topic.value

    @property
    def retention_days(self) -> float:
        """Return retention period in days for readability."""
        return self.retention_ms / (1000 * 60 * 60 * 24)


# Retention constants in milliseconds
_DAYS_MS = 24 * 60 * 60 * 1000
_3_DAYS_MS = 3 * _DAYS_MS
_7_DAYS_MS = 7 * _DAYS_MS
_30_DAYS_MS = 30 * _DAYS_MS


TOPIC_CONFIGS: dict[KafkaTopic, TopicConfig] = {
    KafkaTopic.RAW_CV_UPLOADS: TopicConfig(
        topic=KafkaTopic.RAW_CV_UPLOADS,
        partitions=6,
        retention_ms=_7_DAYS_MS,
        description="Raw CV upload events from the ingestion API",
    ),
    KafkaTopic.RAW_BEHAVIORAL_EVENTS: TopicConfig(
        topic=KafkaTopic.RAW_BEHAVIORAL_EVENTS,
        partitions=12,
        retention_ms=_30_DAYS_MS,
        description="All platform behavioral events (clicks, navigation, forms, etc.)",
    ),
    KafkaTopic.SIGNALS_CV: TopicConfig(
        topic=KafkaTopic.SIGNALS_CV,
        partitions=6,
        retention_ms=_7_DAYS_MS,
        description="DISC signals extracted from parsed CVs",
    ),
    KafkaTopic.SIGNALS_PLATFORM: TopicConfig(
        topic=KafkaTopic.SIGNALS_PLATFORM,
        partitions=12,
        retention_ms=_7_DAYS_MS,
        description="DISC signals extracted from platform behavioral events",
    ),
    KafkaTopic.DISC_SCORE_UPDATES: TopicConfig(
        topic=KafkaTopic.DISC_SCORE_UPDATES,
        partitions=6,
        retention_ms=_3_DAYS_MS,
        description="DISC profile recomputation results",
    ),
    KafkaTopic.RISK_FLAG_EVENTS: TopicConfig(
        topic=KafkaTopic.RISK_FLAG_EVENTS,
        partitions=3,
        retention_ms=_30_DAYS_MS,
        description="Risk flag events from the risk analyzer",
    ),
}
