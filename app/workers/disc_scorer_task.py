"""Celery tasks for DISC profile scoring.

Wraps the DISC scorer service layer, providing async task execution via Celery
with automatic retries and structured logging.
"""

from __future__ import annotations

import asyncio

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.workers.disc_scorer.recompute_disc_profile",
    queue="disc_scoring",
    max_retries=3,
    default_retry_delay=10,
)
def recompute_disc_profile(user_id: str, triggered_by: str = "signal") -> dict:
    """Recompute DISC profiles at 30d/90d/lifetime windows for a user.

    Steps:
        1. Load all signals for the user (placeholder – returns empty for now).
        2. Call :func:`compute_user_disc_profile`.
        3. Trigger downstream risk analysis.
        4. Return results.

    Args:
        user_id: The user whose DISC profile should be recomputed.
        triggered_by: Context label for what triggered this recompute
            (e.g. ``"signal"``, ``"scheduled"``, ``"manual"``).

    Returns:
        dict with DISC profile results and metadata.
    """
    from app.services.disc_scorer.worker import compute_user_disc_profile
    from app.workers.risk_analyzer_task import run_risk_analysis

    log = logger.bind(user_id=user_id, triggered_by=triggered_by)
    log.info("disc_scorer.recompute_start", msg="Starting DISC profile recompute")

    try:
        # ------------------------------------------------------------------
        # 1. Load signals (placeholder – will be wired to DB later)
        # ------------------------------------------------------------------
        signals: list = []
        log.info(
            "disc_scorer.signals_loaded",
            signal_count=len(signals),
            msg="Loaded signals for scoring",
        )

        # ------------------------------------------------------------------
        # 2. Compute DISC profile
        # ------------------------------------------------------------------
        result: dict = asyncio.run(
            compute_user_disc_profile(signals=signals, user_id=user_id)
        )

        log.info(
            "disc_scorer.recompute_complete",
            success=result.get("success"),
            dominant=result.get("dominant"),
            confidence=result.get("confidence"),
            signal_count=result.get("signal_count"),
            msg="DISC profile recompute complete",
        )

        # ------------------------------------------------------------------
        # 3. Trigger downstream risk analysis
        # ------------------------------------------------------------------
        if result.get("success"):
            run_risk_analysis.delay(user_id)
            log.info(
                "disc_scorer.risk_analysis_triggered",
                msg="Triggered downstream risk analysis",
            )

        return {
            "user_id": user_id,
            "triggered_by": triggered_by,
            **result,
        }

    except Exception as exc:
        log.exception(
            "disc_scorer.recompute_failed",
            msg="DISC profile recompute failed",
        )
        raise recompute_disc_profile.retry(exc=exc)


@celery_app.task(
    name="app.workers.disc_scorer.recompute_all_active_users",
    queue="disc_scoring",
)
def recompute_all_active_users() -> dict:
    """Batch recompute DISC profiles for all active users.

    Intended to be called by the Celery Beat scheduler.  Enqueues individual
    :func:`recompute_disc_profile` tasks for each active user.

    Returns:
        dict with the count of users enqueued.
    """
    log = logger.bind(task="recompute_all_active_users")
    log.info("disc_scorer.batch_start", msg="Starting batch DISC recompute")

    # Placeholder – will query active users from DB
    active_user_ids: list[str] = []

    for uid in active_user_ids:
        recompute_disc_profile.delay(uid, triggered_by="scheduled")

    log.info(
        "disc_scorer.batch_enqueued",
        user_count=len(active_user_ids),
        msg="Batch DISC recompute tasks enqueued",
    )

    return {
        "enqueued": len(active_user_ids),
        "status": "ok",
    }
