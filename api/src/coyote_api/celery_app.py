# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""API task publisher, maintenance worker and deployment beat schedule."""

from celery.schedules import crontab
from coyote.application.ingest.messages import INGEST_DISPATCH_TASK, INGEST_WATCH_TASK

from coyote_api.config.runtime_settings import DefaultConfig
from coyote_api.infra.task_queue import create_celery_app

celery_app = create_celery_app("coyote4", include=("coyote_api.tasks.maintenance",))

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
        "task": INGEST_DISPATCH_TASK,
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
                "task": INGEST_WATCH_TASK,
                "schedule": DefaultConfig.COYOTE4_INGEST_WATCH_INTERVAL_SECONDS,
            },
        }
    )
