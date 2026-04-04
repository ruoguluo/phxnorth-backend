"""Celery tasks for risk analysis.

Wraps the risk analyzer service layer, providing async task execution via Celery
with automatic retries and structured logging.
"""

from __future__ import annotations

import asyncio

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.workers.risk_analyzer.run_risk_analysis",
    queue="risk_analysis",
    max_retries=2,
    default_retry_delay=10,
)
def run_risk_analysis(user_id: str) -> dict:
    """Run full risk analysis for a user.

    Steps:
        1. Load the user's DISC profile (placeholder – returns ``None`` for now).
        2. Call :func:`analyze_user_risk`.
        3. Return results.

    Args:
        user_id: The user to run risk analysis for.

    Returns:
        dict with risk analysis results and metadata.
    """
    from app.services.risk_analyzer.worker import analyze_user_risk

    log = logger.bind(user_id=user_id)
    log.info("risk_analyzer.analysis_start", msg="Starting risk analysis")

    try:
        # ------------------------------------------------------------------
        # 1. Load DISC profile data (placeholder – will be wired to DB later)
        # ------------------------------------------------------------------
        cv_profile = None
        platform_profile = None
        disc_profile = None
        preferences = None
        career_analytics: dict = {}
        behavioral_metrics: dict = {}

        log.info(
            "risk_analyzer.profiles_loaded",
            msg="Loaded profiles for risk analysis",
        )

        # ------------------------------------------------------------------
        # 2. Guard: no DISC profile available yet
        # ------------------------------------------------------------------
        if disc_profile is None:
            log.warning(
                "risk_analyzer.no_disc_profile",
                msg="No DISC profile available – skipping risk analysis",
            )
            return {
                "user_id": user_id,
                "success": False,
                "error": "No DISC profile available for user",
                "contradiction": {},
                "risk_assessments": [],
                "red_flags": [],
                "overall_risk_level": "green",
                "flagged_count": 0,
            }

        # ------------------------------------------------------------------
        # 3. Run risk analysis
        # ------------------------------------------------------------------
        result: dict = asyncio.run(
            analyze_user_risk(
                cv_profile=cv_profile,
                platform_profile=platform_profile,
                disc_profile=disc_profile,
                preferences=preferences,
                career_analytics=career_analytics,
                behavioral_metrics=behavioral_metrics,
                user_id=user_id,
            )
        )

        log.info(
            "risk_analyzer.analysis_complete",
            success=result.get("success"),
            overall_risk_level=result.get("overall_risk_level"),
            flagged_count=result.get("flagged_count"),
            red_flag_count=len(result.get("red_flags", [])),
            msg="Risk analysis complete",
        )

        return {
            "user_id": user_id,
            **result,
        }

    except Exception as exc:
        log.exception(
            "risk_analyzer.analysis_failed",
            msg="Risk analysis failed",
        )
        raise run_risk_analysis.retry(exc=exc)


@celery_app.task(
    name="app.workers.risk_analyzer.run_all_active_users",
    queue="risk_analysis",
)
def run_all_active_users() -> dict:
    """Batch risk analysis for all active users.

    Intended to be called by the Celery Beat scheduler.  Enqueues individual
    :func:`run_risk_analysis` tasks for each active user.

    Returns:
        dict with the count of users enqueued.
    """
    log = logger.bind(task="run_all_active_users")
    log.info("risk_analyzer.batch_start", msg="Starting batch risk analysis")

    # Placeholder – will query active users from DB
    active_user_ids: list[str] = []

    for uid in active_user_ids:
        run_risk_analysis.delay(uid)

    log.info(
        "risk_analyzer.batch_enqueued",
        user_count=len(active_user_ids),
        msg="Batch risk analysis tasks enqueued",
    )

    return {
        "enqueued": len(active_user_ids),
        "status": "ok",
    }
