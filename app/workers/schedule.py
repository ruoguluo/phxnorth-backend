"""Celery Beat schedule configuration.

Defines periodic task schedules for background processing including
metric aggregation, DISC recomputation, and risk analysis.
"""

from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    # ── Metric Aggregation ────────────────────────────────────────────
    "aggregate-metrics-30d": {
        "task": "app.workers.metric_aggregator.aggregate_all_users",
        "schedule": crontab(hour="*/2"),  # every 2 hours
        "args": (30,),
    },
    "aggregate-metrics-90d": {
        "task": "app.workers.metric_aggregator.aggregate_all_users",
        "schedule": crontab(hour="4", minute="0"),  # daily at 4:00 AM UTC
        "args": (90,),
    },
    # ── DISC Scoring ──────────────────────────────────────────────────
    "recompute-disc-all-active": {
        "task": "app.workers.disc_scorer.recompute_all_active_users",
        "schedule": crontab(hour="3", minute="30"),  # daily at 3:30 AM UTC
    },
    # ── Risk Analysis ─────────────────────────────────────────────────
    "run-risk-analysis-all": {
        "task": "app.workers.risk_analyzer.run_all_active_users",
        "schedule": crontab(hour="5", minute="0"),  # daily at 5:00 AM UTC
    },
    "contradiction-check-weekly": {
        "task": "app.workers.risk_analyzer.run_all_active_users",
        "schedule": crontab(
            day_of_week="monday", hour="6", minute="0"
        ),  # weekly Monday 6:00 AM UTC
    },
}
