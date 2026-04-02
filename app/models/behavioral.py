"""Behavioral event models for DISC analysis and platform analytics."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class EventType(str, enum.Enum):
    """Types of behavioral events tracked on the platform."""

    # Navigation events
    PAGE_VIEW = "page_view"
    NAVIGATION = "navigation"

    # Interaction events
    CLICK = "click"
    HOVER = "hover"
    SCROLL = "scroll"

    # Form events
    FORM_START = "form_start"
    FORM_SUBMIT = "form_submit"
    FORM_ABANDON = "form_abandon"

    # Assessment events
    ASSESSMENT_START = "assessment_start"
    ASSESSMENT_COMPLETE = "assessment_complete"
    ASSESSMENT_QUESTION_ANSWER = "assessment_question_answer"

    # Career profile events
    PROFILE_UPLOAD = "profile_upload"
    PROFILE_PARSE_COMPLETE = "profile_parse_complete"

    # Communication events
    MESSAGE_SENT = "message_sent"
    NOTIFICATION_OPENED = "notification_opened"

    # Session events
    SESSION_START = "session_start"
    SESSION_END = "session_end"

    # Error events
    ERROR = "error"
    TIMEOUT = "timeout"


class ClientType(str, enum.Enum):
    """Client types for event tracking."""

    WEB = "web"
    MOBILE = "mobile"
    DESKTOP = "desktop"
    API = "api"


class BehavioralEvent(Base):
    """Raw platform events stored in TimescaleDB hypertable.

    Note: Does NOT inherit from BaseModel because TimescaleDB hypertables
    require manual created_at handling without auto-updates.
    """

    __tablename__ = "behavioral_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    event_type: Mapped[EventType] = mapped_column(
        String(60),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    client_type: Mapped[Optional[ClientType]] = mapped_column(
        String(20),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<BehavioralEvent(id={self.id}, user_id={self.user_id}, event_type={self.event_type})>"


class BehavioralMetrics(Base):
    """Aggregated behavioral metrics for DISC analysis."""

    __tablename__ = "behavioral_metrics"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "metric_type",
            "window_days",
            name="uq_behavioral_metrics_user_metric_window",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )
    metric_value: Mapped[float] = mapped_column(
        Numeric(10, 4),
        nullable=False,
    )
    window_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="7 | 30 | 90 | 365 | 0=lifetime",
    )
    sample_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<BehavioralMetrics(user_id={self.user_id}, metric_type={self.metric_type}, window={self.window_days}d)>"
