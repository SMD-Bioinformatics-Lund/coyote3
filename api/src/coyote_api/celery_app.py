# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Celery application for background Coyote4 jobs."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging

from coyote_api.config.runtime_settings import DefaultConfig
from coyote_api.infra.observability.logging import configure_json_logging


@setup_logging.connect
def configure_celery_logging(**kwargs) -> None:
    """Keep worker and beat logs in their own daily files, including task failures."""
    configure_json_logging(
        service_name=DefaultConfig.LOG_SERVICE_NAME,
        level=DefaultConfig.CELERY_LOG_LEVEL,
        log_root=DefaultConfig.LOG_ROOT,
        file_enabled=DefaultConfig.LOG_FILE_ENABLED,
        timezone_name=DefaultConfig.LOG_TIMEZONE,
    )


def _redis_url() -> str:
    """Return the Celery broker/backend URL.

    Celery uses a dedicated runtime value when provided, otherwise it reuses
    the configured Redis cache URL used by the API stack.
    """
    return str(DefaultConfig.CELERY_BROKER_URL or DefaultConfig.CACHE_REDIS_URL or "")


celery_app = Celery(
    "coyote4",
    broker=_redis_url(),
    backend=DefaultConfig.CELERY_RESULT_BACKEND or _redis_url(),
    include=("coyote_api.tasks.ingest", "coyote_api.tasks.maintenance"),
)

celery_app.conf.update(
    timezone=DefaultConfig.LOG_TIMEZONE,
    task_default_queue=DefaultConfig.CELERY_DEFAULT_QUEUE,
    task_track_started=True,
    task_time_limit=DefaultConfig.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=DefaultConfig.CELERY_TASK_SOFT_TIME_LIMIT,
    result_expires=DefaultConfig.CELERY_RESULT_EXPIRES,
    worker_prefetch_multiplier=DefaultConfig.CELERY_WORKER_PREFETCH_MULTIPLIER,
    broker_transport_options={"visibility_timeout": DefaultConfig.CELERY_TASK_TIME_LIMIT + 120},
    result_backend_transport_options={
        "visibility_timeout": DefaultConfig.CELERY_TASK_TIME_LIMIT + 120
    },
    visibility_timeout=DefaultConfig.CELERY_TASK_TIME_LIMIT + 120,
    task_routes={
        "coyote_api.tasks.ingest.*": {"queue": DefaultConfig.CELERY_INGEST_QUEUE},
    },
)

celery_app.conf.beat_schedule = {
    "coyote4-report-artifact-finalization": {
        "task": "coyote_api.tasks.maintenance.finalize_report_artifacts",
        "schedule": 30.0,
    },
    "coyote4-deleted-sample-report-erasure": {
        "task": "coyote_api.tasks.maintenance.erase_deleted_sample_reports",
        "schedule": 30.0,
    },
    "coyote4-audit-event-replay": {
        "task": "coyote_api.tasks.maintenance.replay_audit_events",
        "schedule": 30.0,
    },
    "coyote4-audit-checkpoint-export": {
        "task": "coyote_api.tasks.maintenance.export_audit_checkpoint",
        "schedule": crontab(minute=0),
    },
    "coyote4-notification-email-delivery": {
        "task": "coyote_api.tasks.maintenance.deliver_notification_emails",
        "schedule": 30,
    },
    "coyote4-ingest-job-dispatch": {
        "task": "coyote_api.tasks.ingest.dispatch_pending_jobs",
        "schedule": 30,
    },
    "coyote4-retention-maintenance": {
        "task": "coyote_api.tasks.maintenance.run_retention_maintenance",
        "schedule": crontab(hour=DefaultConfig.COYOTE4_MAINTENANCE_HOUR, minute=0),
    },
    "coyote4-dashboard-metrics-refresh": {
        "task": "coyote_api.tasks.maintenance.refresh_dashboard_metrics",
        "schedule": max(
            30,
            DefaultConfig.DASHBOARD_METRIC_CACHE_TTL_SECONDS // 2,
        ),
    },
}

if DefaultConfig.COYOTE4_INGEST_WATCH_ENABLED:
    celery_app.conf.beat_schedule.update(
        {
            "coyote4-ingest-watch-directory": {
                "task": "coyote_api.tasks.ingest.ingest_watch_directory_once",
                "schedule": DefaultConfig.COYOTE4_INGEST_WATCH_INTERVAL_SECONDS,
            },
        }
    )
