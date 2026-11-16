# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Celery host for core ingestion execution and stable manifest discovery."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from billiard.exceptions import SoftTimeLimitExceeded
from coyote.application.common.observability import timed_operation
from coyote.application.ingest.messages import (
    INGEST_DISPATCH_TASK,
    INGEST_WATCH_TASK,
    ingest_task_name,
)
from coyote.application.ingest.watcher import ManifestWatcher, ManifestWatchSettings
from coyote.application.ingest.worker import IngestJobRunner
from coyote.application.operations.runtime import AccessEvent
from coyote_api.app.application_factory import ingest_job_executor
from coyote_api.app.deps.repositories import get_ingest_jobs_repository
from coyote_api.app.deps.services import (
    get_audit_service,
    get_internal_ingest_service,
    get_notification_service,
)
from coyote_api.config.paths import INGEST_WATCH_DIR
from coyote_api.config.runtime_settings import DefaultConfig
from coyote_api.infra.observability.prometheus_metrics import observe_operation
from coyote_api.tasks.controls import disabled_result, task_family_enabled
from coyote_api.tasks.runtime import ensure_worker_runtime, serializable
from filelock import FileLock, Timeout
from pymongo.errors import ConnectionFailure, PyMongoError

from coyote_relay.celery_app import celery_app

logger = logging.getLogger(__name__)
WATCH_INGEST_DIRECTORY = INGEST_WATCH_DIR
WATCH_INGEST_LOCK_PATH = Path(DefaultConfig.COYOTE4_INGEST_WATCH_LOCK_PATH)


def _record_ingest_audit(event_type: str, message: str, **kwargs: Any) -> None:
    """Submit an ingest audit event without undoing completed ingest work.

    Args:
        event_type: Audit event identifier describing the ingest operation.
        message: Human-readable event summary.
        **kwargs: Audit resource, outcome, severity and metadata fields.

    Notes:
        Events use the data category and celery/ingest tags. An absent audit
        service skips delivery; delivery failures are logged and suppressed.
    """
    audit = get_audit_service()
    if audit is None:
        return
    try:
        kwargs.setdefault("retention_class", "traceability")
        audit.record(event_type, message, category="data", tags=["celery", "ingest"], **kwargs)
    except Exception:
        logger.exception("Ingest audit delivery failed; durable job state is unchanged")


def _retryable_ingest_error(exc: Exception) -> bool:
    """Determine whether an ingest failure should remain eligible for retry.

    Args:
        exc: Failure raised while executing an ingest operation.

    Returns:
        True for connection failures, soft time limits, and MongoDB errors
        labeled TransientTransactionError or UnknownTransactionCommitResult.
    """
    return isinstance(exc, (ConnectionFailure, SoftTimeLimitExceeded)) or (
        isinstance(exc, PyMongoError)
        and (
            exc.has_error_label("TransientTransactionError")
            or exc.has_error_label("UnknownTransactionCommitResult")
        )
    )


def _record_worker_access(event: AccessEvent) -> None:
    """Record the fixed worker's execution grant without logging stored job payloads."""
    _record_ingest_audit(
        "ingest.worker.access",
        "Ingest worker authorized" if event.allowed else "Ingest worker denied",
        actor=event.actor,
        outcome="success" if event.allowed else "denied",
        metadata={"operation": event.operation, "correlation_id": event.correlation_id},
    )


def _cleanup_staging(path: str) -> None:
    """Remove staged upload input after the durable job has completed."""
    shutil.rmtree(path, ignore_errors=True)


def _execute_job(job: dict[str, Any], *, record_completion: Any) -> dict[str, Any]:
    """Bind the current credential verifier and restricted worker identity for execution."""
    return ingest_job_executor(
        get_internal_ingest_service(), audit_access=_record_worker_access
    ).execute(job, record_completion=record_completion)


def _notify_failure(**kwargs: Any) -> None:
    """Deliver an ingestion failure through the configured notification service."""
    get_notification_service().create_notification(**kwargs)


def _execute_ingest_job(job_id: str) -> dict[str, Any]:
    """Execute a fenced job through the core runner and serialize its transport result.

    Args:
        job_id: Identifier of a retained job; no caller-supplied ingest payload is accepted.

    Returns:
        JSON-compatible result, including busy or disabled outcomes.

    Raises:
        ValueError: The job is unknown or has permanently failed.
        Exception: An execution failure was retained for the current claim.
    """
    runner = IngestJobRunner(
        repository=get_ingest_jobs_repository(),
        execute=_execute_job,
        family_enabled=task_family_enabled,
        retryable_error=_retryable_ingest_error,
        audit=_record_ingest_audit,
        notify_failure=_notify_failure,
        cleanup_staging=_cleanup_staging,
        lease_seconds=DefaultConfig.CELERY_TASK_TIME_LIMIT + 60,
        observer=observe_operation,
    )
    return serializable(runner.run(job_id))


def _run_watch_directory_once(task: Any) -> dict[str, Any]:
    """Compose one locked scan with host configuration and durable job execution.

    Args:
        task: Bound Celery task providing the scan's request ID.

    Returns:
        JSON-compatible directory status, scan counts and acknowledgements.
    """
    watcher = ManifestWatcher(
        settings=ManifestWatchSettings(
            directory=WATCH_INGEST_DIRECTORY,
            manifest_name=DefaultConfig.COYOTE4_INGEST_WATCH_FILENAME,
            done_suffix=DefaultConfig.COYOTE4_INGEST_DONE_SUFFIX,
            failed_suffix=DefaultConfig.COYOTE4_INGEST_FAILED_SUFFIX,
            update_existing=DefaultConfig.COYOTE4_INGEST_WATCH_UPDATE_EXISTING,
            increment=DefaultConfig.COYOTE4_INGEST_WATCH_INCREMENT,
        ),
        parse_payload=lambda raw: get_internal_ingest_service().parse_yaml_payload(raw),
        submit_job=lambda **kwargs: get_ingest_jobs_repository().submit(**kwargs),
        execute_job=_execute_ingest_job,
        retryable_error=_retryable_ingest_error,
        audit=_record_ingest_audit,
        observer=observe_operation,
    )
    return serializable(watcher.scan(task_id=task.request.id))


@celery_app.task(name=INGEST_WATCH_TASK, bind=True)
def ingest_watch_directory_once(self: Any) -> dict[str, Any]:
    """Scan the configured ingest folder for coyote4.yaml and ingest each bundle once."""
    ensure_worker_runtime()
    if not task_family_enabled("sample_ingest"):
        return disabled_result("sample_ingest")
    lock = FileLock(WATCH_INGEST_LOCK_PATH)
    try:
        with lock.acquire(timeout=0):
            with timed_operation(
                "ingest.watch_scan", observer=observe_operation, task_id=self.request.id
            ):
                return _run_watch_directory_once(self)
    except Timeout:
        logger.info("celery_ingest_watch_skipped reason=already_running")
        return {"status": "skipped", "reason": "already_running"}


@celery_app.task(
    name=ingest_task_name("sample_bundle"),
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def ingest_sample_bundle_task(self: Any, *, job_id: str) -> dict[str, Any]:
    """Execute a durable job; duplicate delivery cannot repeat a committed bundle."""
    ensure_worker_runtime()
    if not task_family_enabled("sample_ingest"):
        return disabled_result("sample_ingest")
    return _execute_ingest_job(job_id)


@celery_app.task(name=INGEST_DISPATCH_TASK)
def dispatch_pending_jobs() -> dict[str, Any]:
    """Recover accepted jobs after broker loss, worker loss, or dispatch interruption."""
    ensure_worker_runtime()
    dispatched = 0
    kinds = []
    if task_family_enabled("sample_ingest"):
        kinds.append("sample_bundle")
    if task_family_enabled("collection_writes"):
        kinds.extend(["insert_document", "insert_documents", "upsert_document"])
    if not kinds:
        return {"status": "ok", "dispatched": 0}
    for job in get_ingest_jobs_repository().pending(kinds=kinds):
        task = {
            "sample_bundle": ingest_sample_bundle_task,
            "insert_document": insert_collection_document_task,
            "insert_documents": insert_collection_documents_task,
            "upsert_document": upsert_collection_document_task,
        }[job["kind"]]
        task.apply_async(
            kwargs={"job_id": job["_id"]},
            task_id=job["_id"],
            queue=DefaultConfig.CELERY_INGEST_QUEUE,
        )
        dispatched += 1
    return {"status": "ok", "dispatched": dispatched}


@celery_app.task(
    name=ingest_task_name("insert_document"),
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def insert_collection_document_task(
    self: Any,
    *,
    job_id: str,
) -> dict[str, Any]:
    """Insert one validated document into a supported collection."""
    ensure_worker_runtime()
    if not task_family_enabled("collection_writes"):
        return disabled_result("collection_writes")
    return _execute_ingest_job(job_id)


@celery_app.task(
    name=ingest_task_name("insert_documents"),
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def insert_collection_documents_task(
    self: Any,
    *,
    job_id: str,
) -> dict[str, Any]:
    """Insert many validated documents into a supported collection."""
    ensure_worker_runtime()
    if not task_family_enabled("collection_writes"):
        return disabled_result("collection_writes")
    return _execute_ingest_job(job_id)


@celery_app.task(
    name=ingest_task_name("upsert_document"),
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def upsert_collection_document_task(
    self: Any,
    *,
    job_id: str,
) -> dict[str, Any]:
    """Replace/update one validated document in a supported collection."""
    ensure_worker_runtime()
    if not task_family_enabled("collection_writes"):
        return disabled_result("collection_writes")
    return _execute_ingest_job(job_id)
