"""Webhook delivery log model for tracking dispatch outcomes."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class WebhookDelivery(BaseModel):
    """Persistent log of every webhook delivery attempt.

    Each row represents a single dispatch of a payload to a registered
    webhook endpoint.  Rows are created by the
    :func:`~app.workers.webhook_dispatcher_task.dispatch_webhook_task`
    Celery task and are immutable once written (append-only audit log).
    """

    __tablename__ = "webhook_deliveries"

    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )
    status_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    webhook: Mapped["Webhook"] = relationship(  # noqa: F821
        "Webhook",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<WebhookDelivery(id={self.id}, webhook_id={self.webhook_id}, "
            f"event_type={self.event_type!r}, status={self.status!r})>"
        )
