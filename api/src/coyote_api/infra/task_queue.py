# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Configured task transport shared by API publication and installed worker hosts."""

from __future__ import annotations

from celery import Celery
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


def create_celery_app(name: str, *, include: tuple[str, ...]) -> Celery:
    """Build a task host with the deployment's broker and resource limits.

    Args:
        name: Celery application identity used for task registration.
        include: Task modules owned by this host. The API does not load ingestion code.

    Returns:
        Configured application without a scheduler or preloaded task modules.
    """
    celery_app = Celery(
        name,
        broker=_redis_url(),
        backend=DefaultConfig.CELERY_RESULT_BACKEND or _redis_url(),
        include=include,
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
            "coyote_ingest.tasks.*": {"queue": DefaultConfig.CELERY_INGEST_QUEUE},
        },
    )
    return celery_app
