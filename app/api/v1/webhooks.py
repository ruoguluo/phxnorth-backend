"""Webhook registration endpoint.

Allows authenticated users to register callback URLs for specific event
types so they receive real-time notifications when events occur.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.v1.schemas.webhooks import WebhookCreateRequest, WebhookResponse
from app.models.webhook import Webhook

if TYPE_CHECKING:
    from app.models.user import User

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["webhooks"])


# ---------------------------------------------------------------------------
# POST /api/v1/webhooks
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a webhook",
    description=(
        "Register a callback URL to receive notifications for the specified "
        "event types.  A shared secret is required so that outgoing payloads "
        "can be HMAC-signed for verification."
    ),
)
async def register_webhook(
    body: WebhookCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Create a new webhook subscription for the authenticated user."""
    webhook = Webhook(
        user_id=current_user.id,
        url=str(body.url),
        events=[e.value for e in body.events],
        secret=body.secret,
        is_active=True,
    )

    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    logger.info(
        "webhook_registered",
        webhook_id=str(webhook.id),
        user_id=str(current_user.id),
        events=webhook.events,
    )

    return WebhookResponse(
        webhook_id=webhook.id,
        url=webhook.url,
        events=webhook.events,
        created_at=webhook.created_at,
    )
