"""Pydantic schemas for webhook registration endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class WebhookEventType(str, Enum):
    """Supported webhook event types."""

    RISK_FLAG = "risk.flag"
    DISC_UPDATE = "disc.update"


class WebhookCreateRequest(BaseModel):
    """Request body for POST /api/v1/webhooks."""

    url: HttpUrl = Field(description="URL to receive webhook POST requests.")
    events: list[WebhookEventType] = Field(
        min_length=1,
        description="Event types to subscribe to (e.g. ['risk.flag', 'disc.update']).",
    )
    secret: str = Field(
        min_length=16,
        max_length=255,
        description="Shared secret used to sign webhook payloads (HMAC). Min 16 characters.",
    )


class WebhookResponse(BaseModel):
    """Response for POST /api/v1/webhooks (201 Created)."""

    webhook_id: UUID = Field(description="Unique identifier of the registered webhook.")
    url: str = Field(description="Registered callback URL.")
    events: list[str] = Field(description="Subscribed event types.")
    created_at: datetime = Field(description="When the webhook was registered (ISO-8601).")

    model_config = {"from_attributes": True}
