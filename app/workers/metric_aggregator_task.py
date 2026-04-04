"""Metric Aggregator Celery tasks.

Periodic tasks that aggregate behavioral metrics for users over
configurable time windows (e.g. 30-day, 90-day rolling windows).
"""

from __future__ import annotations

import logging
from typing import Any

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.metric_aggregator.aggregate_all_users",
    queue="metrics",
    max_retries=2,
)
def aggregate_all_users(window_days: int = 30) -> dict[str, Any]:
    """Aggregate behavioral metrics for all active users.

    Steps:
      1. Load active users (placeholder)
      2. For each user, compute aggregated metrics for the given window
      3. Store results (placeholder)
      4. Return summary

    Args:
        window_days: Number of days in the rolling aggregation window.

    Returns:
        Summary dict with user count, success/failure counts, and window.
    """
    logger.info("Starting metric aggregation for all users (window=%dd)", window_days)

    # Step 1: Load active users (placeholder)
    # TODO: Replace with actual user repository query
    active_user_ids: list[str] = []
    logger.info("Found %d active users", len(active_user_ids))

    # Step 2 & 3: Compute and store aggregated metrics per user
    succeeded = 0
    failed = 0
    for user_id in active_user_ids:
        try:
            aggregate_user_metrics(user_id, window_days)
            succeeded += 1
        except Exception:
            logger.exception(
                "Failed to aggregate metrics for user %s", user_id
            )
            failed += 1

    summary = {
        "window_days": window_days,
        "total_users": len(active_user_ids),
        "succeeded": succeeded,
        "failed": failed,
    }
    logger.info("Metric aggregation complete: %s", summary)
    return summary


@celery_app.task(
    name="app.workers.metric_aggregator.aggregate_user_metrics",
    queue="metrics",
    max_retries=2,
)
def aggregate_user_metrics(user_id: str, window_days: int = 30) -> dict[str, Any]:
    """Aggregate behavioral metrics for a single user.

    Computes rolling-window aggregates of behavioral signals (DISC scores,
    engagement frequency, risk indicators, etc.) and persists the results.

    Args:
        user_id: The unique identifier of the user.
        window_days: Number of days in the rolling aggregation window.

    Returns:
        Dict with user_id, window, and computed metric summaries.
    """
    logger.info(
        "Aggregating metrics for user %s (window=%dd)", user_id, window_days
    )

    # TODO: Replace with actual metric computation logic
    # 1. Fetch raw behavioral signals from DB within the window
    # 2. Compute aggregates (mean DISC scores, engagement counts, etc.)
    # 3. Persist aggregated snapshot

    result = {
        "user_id": user_id,
        "window_days": window_days,
        "metrics": {},  # placeholder for computed aggregates
        "status": "completed",
    }
    logger.info("Metrics aggregated for user %s", user_id)
    return result
