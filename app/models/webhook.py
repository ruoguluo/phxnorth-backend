"""Webhook registration model for event notification subscriptions."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class Webhook(BaseModel):
    """Webhook subscription for receiving event notifications.

    Users register a URL and a list of event types they want to be notified
    about.  A shared secret is stored so that outgoing payloads can be signed
    (HMAC) for the receiver to verify authenticity.
    """

    __tablename__ = "webhooks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    events: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        default=list,
        nullable=False,
    )
    secret: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Webhook(id={self.id}, user_id={self.user_id}, url={self.url})>"
