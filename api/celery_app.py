"""Celery application for background Coyote3 jobs."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from api.config.runtime_settings import DefaultConfig


def _redis_url() -> str:
    """Return the Celery broker/backend URL.

    Celery uses a dedicated runtime value when provided, otherwise it reuses
    the configured Redis cache URL used by the API stack.
    """
    return str(DefaultConfig.CELERY_BROKER_URL or DefaultConfig.CACHE_REDIS_URL or "")


celery_app = Celery(
    "coyote3",
    broker=_redis_url(),
    backend=DefaultConfig.CELERY_RESULT_BACKEND or _redis_url(),
    include=("api.tasks.ingest", "api.tasks.maintenance"),
)

celery_app.conf.update(
    task_default_queue=DefaultConfig.CELERY_DEFAULT_QUEUE,
    task_track_started=True,
    task_time_limit=DefaultConfig.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=DefaultConfig.CELERY_TASK_SOFT_TIME_LIMIT,
    result_expires=DefaultConfig.CELERY_RESULT_EXPIRES,
    worker_prefetch_multiplier=DefaultConfig.CELERY_WORKER_PREFETCH_MULTIPLIER,
    task_routes={
        "api.tasks.ingest.*": {"queue": DefaultConfig.CELERY_INGEST_QUEUE},
    },
)

celery_app.conf.beat_schedule = {
    "coyote3-retention-maintenance": {
        "task": "api.tasks.maintenance.run_retention_maintenance",
        "schedule": crontab(hour=DefaultConfig.COYOTE3_MAINTENANCE_HOUR, minute=0),
    },
    "coyote3-dashboard-metrics-refresh": {
        "task": "api.tasks.maintenance.refresh_dashboard_metrics",
        "schedule": max(
            30,
            DefaultConfig.DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS // 2,
        ),
    },
}

if DefaultConfig.COYOTE3_INGEST_WATCH_ENABLED:
    celery_app.conf.beat_schedule.update(
        {
            "coyote3-ingest-watch-directory": {
                "task": "api.tasks.ingest.ingest_watch_directory_once",
                "schedule": DefaultConfig.COYOTE3_INGEST_WATCH_INTERVAL_SECONDS,
            },
        }
    )
