"""Celery application factory and configuration.

Configures Celery with Redis as both broker and result backend.
Tasks are routed to dedicated queues per worker domain.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "phxnorth",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Reliability
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Routing
    task_routes={
        "app.workers.cv_parser.*": {"queue": "cv_parsing"},
        "app.workers.signal_extractor.*": {"queue": "signal_extraction"},
        "app.workers.disc_scorer.*": {"queue": "disc_scoring"},
        "app.workers.risk_analyzer.*": {"queue": "risk_analysis"},
        "app.workers.metric_aggregator.*": {"queue": "metrics"},
        "app.workers.webhook_dispatcher.*": {"queue": "webhooks"},
    },
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
)

# Auto-discover tasks in worker modules
celery_app.autodiscover_tasks([
    "app.workers",
])
