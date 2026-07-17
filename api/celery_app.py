"""Celery application for background Coyote3 jobs."""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

from api.config import configure_process_env


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _redis_url() -> str:
    """Return the Celery broker/backend URL.

    Celery uses a dedicated env var when provided, otherwise it reuses the
    configured Redis cache URL used by the API stack.
    """
    configure_process_env()
    return (
        os.getenv("CELERY_BROKER_URL") or os.getenv("CACHE_REDIS_URL") or "redis://localhost:6379/0"
    )


celery_app = Celery(
    "coyote3",
    broker=_redis_url(),
    backend=os.getenv("CELERY_RESULT_BACKEND") or _redis_url(),
    include=("api.tasks.ingest", "api.tasks.maintenance"),
)

celery_app.conf.update(
    task_default_queue=os.getenv("CELERY_DEFAULT_QUEUE", "default"),
    task_track_started=True,
    task_time_limit=int(os.getenv("CELERY_TASK_TIME_LIMIT", "7200")),
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "6900")),
    result_expires=int(os.getenv("CELERY_RESULT_EXPIRES", "86400")),
    worker_prefetch_multiplier=int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1")),
    task_routes={
        "api.tasks.ingest.*": {"queue": os.getenv("CELERY_INGEST_QUEUE", "ingest")},
    },
)

celery_app.conf.beat_schedule = {
    "coyote3-retention-maintenance": {
        "task": "api.tasks.maintenance.run_retention_maintenance",
        "schedule": crontab(hour=int(os.getenv("COYOTE3_MAINTENANCE_HOUR", "2")), minute=0),
    },
}

if _truthy(os.getenv("COYOTE3_INGEST_WATCH_ENABLED")):
    celery_app.conf.beat_schedule.update(
        {
        "coyote3-ingest-watch-directory": {
            "task": "api.tasks.ingest.ingest_watch_directory_once",
            "schedule": int(os.getenv("COYOTE3_INGEST_WATCH_INTERVAL_SECONDS", "30")),
        },
        }
    )
