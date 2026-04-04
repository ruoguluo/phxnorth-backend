"""Kafka message schemas as Pydantic dataclasses.

Each schema represents a message type flowing through the Kafka pipeline.
All schemas provide to_dict() for serialization and from_dict() for
deserialization, ensuring consistent encoding across producers and consumers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import Field
from pydantic.dataclasses import dataclass


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def _new_id() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


@dataclass(frozen=True)
class CVUploadMessage:
    """Message produced when a CV is uploaded for processing.

    Published to: raw.cv.uploads
    """

    user_id: str
    source: str
    s3_key: str
    raw_text: str
    filename: str
    event_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "source": self.source,
            "s3_key": self.s3_key,
            "raw_text": self.raw_text,
            "filename": self.filename,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CVUploadMessage:
        """Deserialize from a dictionary."""
        data = dict(data)
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass(frozen=True)
class BehavioralEventMessage:
    """Message produced for each platform behavioral event.

    Published to: raw.behavioral.events
    """

    user_id: str
    session_id: str
    event_type: str
    payload: dict[str, Any]
    latency_ms: Optional[int] = None
    client_type: Optional[str] = None
    event_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "latency_ms": self.latency_ms,
            "client_type": self.client_type,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BehavioralEventMessage:
        """Deserialize from a dictionary."""
        data = dict(data)
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass(frozen=True)
class SignalMessage:
    """Message produced when a DISC signal is extracted from a source.

    Published to: signals.cv or signals.platform
    """

    user_id: str
    signal_type: str
    confidence: float
    source: str
    evidence: dict[str, Any]
    ttl_days: int = 30
    signal_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "signal_id": self.signal_id,
            "user_id": self.user_id,
            "signal_type": self.signal_type,
            "confidence": self.confidence,
            "source": self.source,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
            "ttl_days": self.ttl_days,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignalMessage:
        """Deserialize from a dictionary."""
        data = dict(data)
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass(frozen=True)
class DISCUpdateMessage:
    """Message produced when a user's DISC profile is recomputed.

    Published to: disc.score.updates
    """

    user_id: str
    d_score: float
    i_score: float
    s_score: float
    c_score: float
    dominant: str
    secondary: Optional[str] = None
    confidence: float = 0.0
    window_days: int = 30
    contradiction_score: float = 0.0
    shift_detected: bool = False
    computed_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "user_id": self.user_id,
            "d_score": self.d_score,
            "i_score": self.i_score,
            "s_score": self.s_score,
            "c_score": self.c_score,
            "dominant": self.dominant,
            "secondary": self.secondary,
            "confidence": self.confidence,
            "window_days": self.window_days,
            "contradiction_score": self.contradiction_score,
            "shift_detected": self.shift_detected,
            "computed_at": self.computed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DISCUpdateMessage:
        """Deserialize from a dictionary."""
        data = dict(data)
        if isinstance(data.get("computed_at"), str):
            data["computed_at"] = datetime.fromisoformat(data["computed_at"])
        return cls(**data)


@dataclass(frozen=True)
class RiskFlagMessage:
    """Message produced when a risk flag is generated or updated.

    Published to: risk.flag.events
    """

    user_id: str
    category: str
    score: float
    severity: str
    is_flagged: bool = False
    evidence: Optional[dict[str, Any]] = None
    computed_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "user_id": self.user_id,
            "category": self.category,
            "score": self.score,
            "severity": self.severity,
            "is_flagged": self.is_flagged,
            "evidence": self.evidence,
            "computed_at": self.computed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskFlagMessage:
        """Deserialize from a dictionary."""
        data = dict(data)
        if isinstance(data.get("computed_at"), str):
            data["computed_at"] = datetime.fromisoformat(data["computed_at"])
        return cls(**data)
