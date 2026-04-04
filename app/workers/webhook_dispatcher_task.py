"""Celery tasks for webhook dispatch and delivery logging.

Provides two tasks:

* :func:`dispatch_webhook_task` – delivers a single webhook to its registered
  endpoint, logging the result as a :class:`~app.models.webhook_delivery.WebhookDelivery`.
* :func:`dispatch_event_to_webhooks` – fans out delivery to all active
  webhooks subscribed to a given event type.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.workers.webhook_dispatcher.dispatch_webhook",
    queue="webhooks",
    max_retries=5,
    default_retry_delay=60,
    bind=True,
)
def dispatch_webhook_task(
    self,
    webhook_id: str,
    event_type: str,
    payload: dict,
) -> dict:
    """Deliver a webhook to its registered endpoint.

    Steps:
        1. Load webhook config (url, secret) from DB.
        2. Call :func:`dispatch_webhook_with_retry`.
        3. Log delivery result as a :class:`WebhookDelivery` row.

    Args:
        webhook_id: UUID of the webhook registration to deliver to.
        event_type: The event type string (e.g. ``"disc.profile.updated"``).
        payload: JSON-serialisable dict to send as the request body.

    Returns:
        dict with delivery outcome metadata.
    """
    log = logger.bind(webhook_id=webhook_id, event_type=event_type)
    log.info(
        "webhook_dispatcher.dispatch_start",
        msg="Starting webhook delivery",
    )

    try:
        # ------------------------------------------------------------------
        # 1. Load webhook config (placeholder – will wire to DB session)
        # ------------------------------------------------------------------
        # TODO: Replace with real DB lookup once async session is available
        #   webhook = await session.get(Webhook, webhook_id)
        webhook_url: str | None = None
        webhook_secret: str | None = None

        if not webhook_url or not webhook_secret:
            log.warning(
                "webhook_dispatcher.webhook_not_found",
                msg="Webhook config not found or inactive; skipping delivery",
            )
            return {
                "webhook_id": webhook_id,
                "event_type": event_type,
                "status": "skipped",
                "error": "Webhook not found or inactive",
            }

        # ------------------------------------------------------------------
        # 2. Dispatch with retry
        # ------------------------------------------------------------------
        from app.services.webhook.dispatcher import dispatch_webhook_with_retry

        result: dict = asyncio.run(
            dispatch_webhook_with_retry(
                url=webhook_url,
                payload=payload,
                secret=webhook_secret,
                event_type=event_type,
            )
        )

        status = "success" if result.get("success") else "failed"

        log.info(
            "webhook_dispatcher.dispatch_complete",
            status=status,
            status_code=result.get("status_code"),
            attempts=result.get("attempts"),
            duration_ms=result.get("duration_ms"),
            msg="Webhook delivery complete",
        )

        # ------------------------------------------------------------------
        # 3. Log delivery result (placeholder – will wire to DB session)
        # ------------------------------------------------------------------
        # TODO: Persist WebhookDelivery row once async session is available
        #   delivery = WebhookDelivery(
        #       webhook_id=webhook_id,
        #       event_type=event_type,
        #       payload=payload,
        #       status=status,
        #       status_code=result.get("status_code"),
        #       error=result.get("error"),
        #       duration_ms=result.get("duration_ms"),
        #       attempt_count=result.get("attempts", 1),
        #       delivered_at=datetime.now(timezone.utc) if status == "success" else None,
        #   )
        #   session.add(delivery)
        #   await session.commit()

        return {
            "webhook_id": webhook_id,
            "event_type": event_type,
            "status": status,
            "status_code": result.get("status_code"),
            "duration_ms": result.get("duration_ms"),
            "attempts": result.get("attempts", 1),
            "delivery_id": result.get("delivery_id"),
        }

    except Exception as exc:
        log.exception(
            "webhook_dispatcher.dispatch_failed",
            msg="Webhook delivery failed, scheduling retry",
        )
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.webhook_dispatcher.dispatch_event_to_webhooks",
    queue="webhooks",
)
def dispatch_event_to_webhooks(event_type: str, payload: dict) -> dict:
    """Fan out delivery to all active webhooks subscribed to an event type.

    Queries for active webhooks whose ``events`` array contains the given
    *event_type* and enqueues a :func:`dispatch_webhook_task` for each match.

    Args:
        event_type: The event type string to match against webhook subscriptions.
        payload: JSON-serialisable dict to deliver to each matching webhook.

    Returns:
        dict with the count of dispatched tasks.
    """
    log = logger.bind(event_type=event_type)
    log.info(
        "webhook_dispatcher.fan_out_start",
        msg="Finding webhooks subscribed to event",
    )

    # ------------------------------------------------------------------
    # Load matching webhooks (placeholder – will wire to DB session)
    # ------------------------------------------------------------------
    # TODO: Replace with real query once async session is available
    #   webhooks = await session.execute(
    #       select(Webhook).where(
    #           Webhook.is_active == True,
    #           Webhook.events.contains([event_type]),
    #       )
    #   )
    matching_webhook_ids: list[str] = []

    for wh_id in matching_webhook_ids:
        dispatch_webhook_task.delay(wh_id, event_type, payload)

    log.info(
        "webhook_dispatcher.fan_out_complete",
        dispatched=len(matching_webhook_ids),
        msg="Webhook fan-out tasks enqueued",
    )

    return {
        "event_type": event_type,
        "dispatched": len(matching_webhook_ids),
        "status": "ok",
    }
