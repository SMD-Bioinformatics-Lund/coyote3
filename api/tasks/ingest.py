"""Celery tasks that execute validated internal ingest workflows."""

from __future__ import annotations

import logging
import shutil
from hashlib import sha256
from pathlib import Path
from typing import Any

from billiard.exceptions import SoftTimeLimitExceeded
from filelock import FileLock, Timeout
from pydantic import ValidationError
from pymongo.errors import ConnectionFailure, PyMongoError

from api.app.container import util
from api.app.deps.repositories import get_ingest_jobs_repository
from api.app.deps.services import (
    get_audit_service,
    get_internal_ingest_service,
    get_notification_service,
)
from api.app.lifecycle import ensure_runtime_initialized
from api.celery_app import celery_app
from api.config import get_runtime_mode_flags
from api.config.paths import INGEST_WATCH_DIR
from api.config.runtime_settings import DefaultConfig
from api.contracts.schemas.samples import SAMPLE_SOURCE_PATH_KEYS
from api.domain.core.exceptions import AppError
from api.infra.observability.operations import timed_operation
from api.tasks.controls import disabled_result, task_family_enabled

logger = logging.getLogger(__name__)
WATCH_INGEST_DIRECTORY = INGEST_WATCH_DIR
WATCH_INGEST_LOCK_PATH = Path(DefaultConfig.COYOTE3_INGEST_WATCH_LOCK_PATH)


def _ingest_failure_message(exc: Exception, *, retryable: bool) -> str:
    """Expose validation explanations without serializing internal exception details."""
    if retryable:
        return "Temporary service failure; ingestion will be retried"
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
            for item in exc.errors(include_input=False, include_context=False, include_url=False)
        )[:450]
    if isinstance(exc, FileNotFoundError):
        return str(exc)[:450]
    if isinstance(exc, PermissionError):
        return f"Permission denied reading or writing '{Path(exc.filename).name if exc.filename else 'ingest storage'}'; check application UID/GID and directory permissions."
    if isinstance(exc, ValueError) or (isinstance(exc, AppError) and exc.status_code < 500):
        return str(exc)[:450] or "Ingest validation failed"
    return "Ingest write failed; contact an administrator with the task ID"


def _ensure_worker_runtime() -> None:
    """Initialize runtime dependencies in the Celery worker process."""
    mode_flags = get_runtime_mode_flags()
    ensure_runtime_initialized(
        testing=mode_flags["testing"],
        development=mode_flags["development"],
    )


def _serializable(payload: Any) -> Any:
    """Convert ingest results for Celery's JSON result transport.

    Args:
        payload: Result containing nested mappings, sequences and BSON values.

    Returns:
        The result after conversion by the shared serialization utility.
    """
    return util.common.convert_to_serializable(payload)


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
        audit.record(event_type, message, category="data", tags=["celery", "ingest"], **kwargs)
    except Exception:
        logger.exception("Ingest audit delivery failed; durable job state is unchanged")


def _retryable_ingest_error(exc):
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


def _unique_marker_path(manifest_path: Path, suffix: str, task_id: str | None) -> Path:
    """Choose the acknowledgement filename for a watched manifest.

    Args:
        manifest_path: Source manifest path; the marker stays in its directory.
        suffix: Completion or failure suffix appended to the filename.
        task_id: Task token appended if the initial marker already exists;
            None uses retry as the token.

    Returns:
        Candidate marker path. The task-suffixed candidate is not checked for
        an existing file, and this helper does not create or rename files.
    """
    marker_path = manifest_path.with_name(f"{manifest_path.name}{suffix}")
    if not marker_path.exists():
        return marker_path
    task_token = task_id or "retry"
    return manifest_path.with_name(f"{manifest_path.name}{suffix}.{task_token}")


def _translate_payload_source_path(value: Any, manifest_path: Path) -> Any:
    """Resolve a manifest-relative path to a container-visible filesystem path."""
    if isinstance(value, dict):
        translated = dict(value)
        if translated.get("path"):
            translated["path"] = str(
                _translate_payload_source_path(translated["path"], manifest_path)
            )
        return translated
    path_value = Path(str(value))
    if not path_value.is_absolute():
        path_value = (manifest_path.parent / path_value).resolve()
    return str(path_value)


def _resolve_relative_sample_paths(payload: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    """Resolve manifest file paths to paths visible from API/worker containers."""
    resolved = dict(payload)
    for key in SAMPLE_SOURCE_PATH_KEYS:
        if resolved.get(key):
            resolved[key] = _translate_payload_source_path(resolved[key], manifest_path)
    files = resolved.get("files")
    if isinstance(files, dict):
        resolved["files"] = {
            key: _translate_payload_source_path(value, manifest_path)
            if key in SAMPLE_SOURCE_PATH_KEYS and value
            else value
            for key, value in files.items()
        }
    return resolved


def _run_watch_directory_once(self) -> dict[str, Any]:
    """Discover stable manifests and execute their durable ingest jobs.

    Returns:
        Directory status, or scan counts and successful/failed acknowledgements.

    Notes:
        Uses the bound task's request ID for tracing and marker names. The caller
        owns the scan lock. Jobs are submitted before execution; changed manifests
        and retryable failures remain for a later scan. Busy or disabled jobs are
        skipped without a completion marker or success audit, preserving their
        manifests for later processing. An acknowledgement failure does not undo
        committed data. Nonretryable failures receive a failure marker when
        directory permissions allow it.
    """
    watch_dir = WATCH_INGEST_DIRECTORY
    if not watch_dir.exists():
        return {"status": "not_found", "watch_dir": str(watch_dir), "scanned": 0}
    if not watch_dir.is_dir():
        return {"status": "invalid", "watch_dir": str(watch_dir), "reason": "not a directory"}

    manifest_name = DefaultConfig.COYOTE3_INGEST_WATCH_FILENAME
    done_suffix = DefaultConfig.COYOTE3_INGEST_DONE_SUFFIX
    failed_suffix = DefaultConfig.COYOTE3_INGEST_FAILED_SUFFIX
    allow_update = DefaultConfig.COYOTE3_INGEST_WATCH_UPDATE_EXISTING
    increment = DefaultConfig.COYOTE3_INGEST_WATCH_INCREMENT

    manifests = sorted(path for path in watch_dir.rglob(manifest_name) if path.is_file())
    service = get_internal_ingest_service()
    ingested: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []

    for manifest_path in manifests:
        try:
            task_context = {"task_id": self.request.id, "manifest": str(manifest_path)}
            with timed_operation("ingest.manifest_parse", **task_context):
                before = manifest_path.stat()
                manifest_bytes = manifest_path.read_bytes()
                after = manifest_path.stat()
                if (before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_ino,
                    after.st_size,
                    after.st_mtime_ns,
                ):
                    logger.warning("Manifest changed during discovery; deferred to next scan")
                    continue
                payload = service.parse_yaml_payload(manifest_bytes.decode("utf-8"))
                payload = _resolve_relative_sample_paths(payload, manifest_path)
            with timed_operation("ingest.sample_bundle", **task_context):
                identity = sha256(
                    f"{manifest_path.resolve()}:{after.st_mtime_ns}:".encode() + manifest_bytes
                ).hexdigest()
                get_ingest_jobs_repository().submit(
                    job_id=identity,
                    source_payload=payload,
                    update_existing=allow_update,
                    increment=increment,
                    submitted_by="ingest-watcher",
                )
                result = _execute_ingest_job(identity)
                if result.get("status") in {"busy", "disabled"}:
                    continue
            done_path = _unique_marker_path(manifest_path, done_suffix, self.request.id)
            try:
                manifest_path.rename(done_path)
            except OSError:
                logger.exception("Ingest committed; manifest acknowledgement remains pending")
                continue
            ingested.append(
                {
                    "manifest": str(manifest_path),
                    "done_path": str(done_path),
                    "sample_id": str(result.get("sample_id", "")),
                    "sample_name": str(result.get("sample_name", "")),
                }
            )
            _record_ingest_audit(
                "ingest.watch.succeeded",
                "Watched manifest ingested",
                resource_type="sample",
                resource_id=str(result.get("sample_id", "")),
                resource_name=str(result.get("sample_name", "")),
                metadata={
                    "manifest": str(manifest_path),
                    "done_path": str(done_path),
                    "task_id": self.request.id,
                    "counts": result.get("counts") or result.get("data_counts"),
                },
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.exception("celery_ingest_watch_failed manifest=%s", manifest_path)
            if _retryable_ingest_error(exc):
                continue
            failed_path = _unique_marker_path(manifest_path, failed_suffix, self.request.id)
            try:
                manifest_path.rename(failed_path)
                marker_path = str(failed_path)
            except OSError:
                marker_path = ""
            failed.append(
                {
                    "manifest": str(manifest_path),
                    "failed_path": marker_path,
                    "error": str(exc),
                }
            )
            _record_ingest_audit(
                "ingest.watch.failed",
                f"Watched manifest ingest failed: {_ingest_failure_message(exc, retryable=False)}",
                severity="error",
                outcome="failure",
                resource_type="manifest",
                resource_id=str(manifest_path),
                metadata={
                    "manifest": str(manifest_path),
                    "failed_path": marker_path,
                    "task_id": self.request.id,
                    "error": str(exc),
                },
            )

    return _serializable(
        {
            "status": "ok",
            "watch_dir": str(watch_dir),
            "manifest": manifest_name,
            "scanned": len(manifests),
            "ingested": ingested,
            "failed": failed,
        }
    )


@celery_app.task(name="api.tasks.ingest.ingest_watch_directory_once", bind=True)
def ingest_watch_directory_once(self) -> dict[str, Any]:
    """Scan the configured ingest folder for coyote3.yaml and ingest each bundle once."""
    _ensure_worker_runtime()
    if not task_family_enabled("sample_ingest"):
        return disabled_result("sample_ingest")
    lock = FileLock(WATCH_INGEST_LOCK_PATH)
    try:
        with lock.acquire(timeout=0):
            with timed_operation("ingest.watch_scan", task_id=self.request.id):
                return _run_watch_directory_once(self)
    except Timeout:
        logger.info("celery_ingest_watch_skipped reason=already_running")
        return {"status": "skipped", "reason": "already_running"}


def _execute_ingest_job(job_id: str) -> dict[str, Any]:
    """Claim a durable ingest job and record completion with its data writes.

    Args:
        job_id: Identifier of a previously submitted job.

    Returns:
        Serialized ingest result, a busy status when another worker owns the
        lease, or a disabled status when the job's task family is disabled.
        Previously successful jobs return their stored result.

    Raises:
        ValueError: The job does not exist or has already failed permanently.

    Notes:
        Completion is recorded through the ingest service's transaction callback.
        Execution failures update retry state and propagate unless a committed
        result is found. Successful jobs remove their staging directory and emit
        a best-effort audit event.
    """
    repository = get_ingest_jobs_repository()
    existing = repository.get(job_id)
    if existing is None:
        raise ValueError("Ingest job not found")
    family = "sample_ingest" if existing["kind"] == "sample_bundle" else "collection_writes"
    if not task_family_enabled(family):
        return disabled_result(family)
    if existing["state"] == "succeeded":
        if existing.get("staging_dir"):
            shutil.rmtree(existing["staging_dir"], ignore_errors=True)
        return _serializable(existing["result"])
    if existing["state"] == "failed":
        raise ValueError(existing.get("error") or "Ingest job failed")
    job = repository.claim(job_id, lease_seconds=DefaultConfig.CELERY_TASK_TIME_LIMIT + 60)
    if job is None:
        return {"status": "busy", "job_id": job_id}
    try:
        with timed_operation("ingest.sample_bundle", task_id=job_id):
            service = get_internal_ingest_service()

            def completion(result, session):
                """Complete the leased job within the ingest transaction.

                Args:
                    result: Ingest result to persist for duplicate delivery.
                    session: MongoDB session owning the corresponding data writes.
                """
                repository.complete(job_id, job["lease_token"], result, session)

            if job["kind"] == "sample_bundle":
                source_payload = dict(job["source_payload"])
                for warning in source_payload.pop("_ingest_warnings", []):
                    _record_ingest_audit(
                        "ingest.bundle.files_ignored",
                        warning,
                        severity="warning",
                        outcome="warning",
                        actor=job.get("submitted_by"),
                        metadata={"task_id": job_id},
                    )
                result = service.ingest_sample_bundle(
                    source_payload,
                    allow_update=job["update_existing"],
                    increment=job["increment"],
                    record_completion=completion,
                )
            else:
                operation = {
                    "insert_document": service.insert_collection_document,
                    "insert_documents": service.insert_collection_documents,
                    "upsert_document": service.upsert_collection_document,
                }[job["kind"]]
                result = operation(**job["source_payload"], record_completion=completion)
    except Exception as exc:
        retryable = _retryable_ingest_error(exc)
        error = _ingest_failure_message(exc, retryable=retryable)
        logger.exception("Ingest task %s failed: %s", job_id, error)
        repository.fail(job_id, job["lease_token"], retryable=retryable, error=error)
        committed = repository.get(job_id)
        if committed is not None and committed["state"] == "succeeded":
            result = committed["result"]
        else:
            _record_ingest_audit(
                "ingest.bundle.failed",
                f"Ingest attempt failed: {error}",
                severity="error",
                outcome="failure",
                actor=job.get("submitted_by"),
                metadata={"task_id": job_id, "retryable": retryable, "error": error},
            )
            if not retryable and job.get("submitted_by"):
                try:
                    get_notification_service().create_notification(
                        audience="users",
                        recipients=[job["submitted_by"]],
                        tone="error",
                        category="application",
                        title="Ingest failed",
                        message=f"{error}\nTask ID: {job_id}",
                        source="Ingest workspace",
                        created_by="system",
                        severity="warning",
                        resource={"type": "ingest", "id": job_id},
                    )
                except Exception:
                    logger.exception(
                        "Could not deliver failure notification for ingest task %s", job_id
                    )
            raise
    if job.get("staging_dir"):
        shutil.rmtree(job["staging_dir"], ignore_errors=True)
    try:
        _record_ingest_audit(
            "ingest.bundle.succeeded",
            "Sample bundle ingested",
            resource_type="sample",
            resource_id=str(result.get("sample_id", "")),
            resource_name=str(result.get("sample_name", "")),
            metadata={
                "task_id": job_id,
                "counts": result.get("counts") or result.get("data_counts"),
            },
        )
    except Exception:
        logger.exception("Ingest committed; audit delivery failed")
    return _serializable(result)


@celery_app.task(
    name="api.tasks.ingest.ingest_sample_bundle",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def ingest_sample_bundle_task(self, *, job_id: str) -> dict[str, Any]:
    """Execute a durable job; duplicate delivery cannot repeat a committed bundle."""
    _ensure_worker_runtime()
    if not task_family_enabled("sample_ingest"):
        return disabled_result("sample_ingest")
    return _execute_ingest_job(job_id)


@celery_app.task(name="api.tasks.ingest.dispatch_pending_jobs")
def dispatch_pending_jobs() -> dict[str, Any]:
    """Recover accepted jobs after broker loss, worker loss, or dispatch interruption."""
    _ensure_worker_runtime()
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
    name="api.tasks.ingest.insert_collection_document",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def insert_collection_document_task(
    self,
    *,
    job_id: str,
) -> dict[str, Any]:
    """Insert one validated document into a supported collection."""
    _ensure_worker_runtime()
    if not task_family_enabled("collection_writes"):
        return disabled_result("collection_writes")
    return _execute_ingest_job(job_id)


@celery_app.task(
    name="api.tasks.ingest.insert_collection_documents",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def insert_collection_documents_task(
    self,
    *,
    job_id: str,
) -> dict[str, Any]:
    """Insert many validated documents into a supported collection."""
    _ensure_worker_runtime()
    if not task_family_enabled("collection_writes"):
        return disabled_result("collection_writes")
    return _execute_ingest_job(job_id)


@celery_app.task(
    name="api.tasks.ingest.upsert_collection_document",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def upsert_collection_document_task(
    self,
    *,
    job_id: str,
) -> dict[str, Any]:
    """Replace/update one validated document in a supported collection."""
    _ensure_worker_runtime()
    if not task_family_enabled("collection_writes"):
        return disabled_result("collection_writes")
    return _execute_ingest_job(job_id)
