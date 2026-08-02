"""Celery tasks that execute validated internal ingest workflows."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from celery.utils.log import get_task_logger
from filelock import FileLock, Timeout

from api.app.container import util
from api.app.deps.services import get_audit_service, get_internal_ingest_service
from api.app.lifecycle import ensure_runtime_initialized
from api.celery_app import celery_app
from api.config import get_runtime_mode_flags
from api.config.paths import INGEST_WATCH_DIR
from api.config.runtime_settings import DefaultConfig
from api.contracts.schemas.samples import SAMPLE_SOURCE_PATH_KEYS
from api.tasks.controls import disabled_result, task_family_enabled

logger = get_task_logger(__name__)
WATCH_INGEST_DIRECTORY = INGEST_WATCH_DIR
WATCH_INGEST_LOCK_PATH = Path(DefaultConfig.COYOTE3_INGEST_WATCH_LOCK_PATH)


def _ensure_worker_runtime() -> None:
    """Initialize runtime dependencies in the Celery worker process."""
    mode_flags = get_runtime_mode_flags()
    ensure_runtime_initialized(
        testing=mode_flags["testing"],
        development=mode_flags["development"],
    )


def _serializable(payload: Any) -> Any:
    return util.common.convert_to_serializable(payload)


def _record_ingest_audit(event_type: str, message: str, **kwargs: Any) -> None:
    audit = get_audit_service()
    if audit is None:
        return
    audit.record(
        event_type,
        message,
        category="data",
        tags=["celery", "ingest"],
        **kwargs,
    )


def _unique_marker_path(manifest_path: Path, suffix: str, task_id: str | None) -> Path:
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
            payload = service.parse_yaml_payload(manifest_path.read_text(encoding="utf-8"))
            payload = _resolve_relative_sample_paths(payload, manifest_path)
            result = service.ingest_sample_bundle(
                payload,
                allow_update=allow_update,
                increment=increment,
            )
            done_path = _unique_marker_path(manifest_path, done_suffix, self.request.id)
            manifest_path.rename(done_path)
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
                "Watched manifest ingest failed",
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
            return _run_watch_directory_once(self)
    except Timeout:
        logger.info("celery_ingest_watch_skipped reason=already_running")
        return {"status": "skipped", "reason": "already_running"}


@celery_app.task(name="api.tasks.ingest.ingest_sample_bundle", bind=True)
def ingest_sample_bundle_task(
    self,
    *,
    source_payload: dict[str, Any],
    update_existing: bool = False,
    increment: bool = False,
    staging_dir: str | None = None,
) -> dict[str, Any]:
    """Create or update a sample bundle through the internal ingest service."""
    _ensure_worker_runtime()
    if not task_family_enabled("sample_ingest"):
        return disabled_result("sample_ingest")
    logger.info("celery_ingest_sample_bundle_started task_id=%s", self.request.id)
    try:
        result = get_internal_ingest_service().ingest_sample_bundle(
            source_payload,
            allow_update=update_existing,
            increment=increment,
        )
        logger.info("celery_ingest_sample_bundle_finished task_id=%s", self.request.id)
        _record_ingest_audit(
            "ingest.bundle.succeeded",
            "Sample bundle ingested",
            resource_type="sample",
            resource_id=str(result.get("sample_id", "")),
            resource_name=str(result.get("sample_name", "")),
            metadata={
                "task_id": self.request.id,
                "counts": result.get("counts") or result.get("data_counts"),
            },
        )
        return _serializable(result)
    except Exception as exc:
        _record_ingest_audit(
            "ingest.bundle.failed",
            "Sample bundle ingest failed",
            severity="error",
            outcome="failure",
            metadata={"task_id": self.request.id, "error": str(exc)},
        )
        raise
    finally:
        if staging_dir:
            shutil.rmtree(staging_dir, ignore_errors=True)


@celery_app.task(name="api.tasks.ingest.insert_collection_document", bind=True)
def insert_collection_document_task(
    self,
    *,
    collection: str,
    document: dict[str, Any],
    ignore_duplicate: bool = False,
) -> dict[str, Any]:
    """Insert one validated document into a supported collection."""
    _ensure_worker_runtime()
    if not task_family_enabled("collection_writes"):
        return disabled_result("collection_writes")
    logger.info(
        "celery_insert_collection_document_started task_id=%s collection=%s",
        self.request.id,
        collection,
    )
    result = get_internal_ingest_service().insert_collection_document(
        collection=collection,
        document=document,
        ignore_duplicate=ignore_duplicate,
    )
    return _serializable(result)


@celery_app.task(name="api.tasks.ingest.insert_collection_documents", bind=True)
def insert_collection_documents_task(
    self,
    *,
    collection: str,
    documents: list[dict[str, Any]],
    ignore_duplicates: bool = False,
) -> dict[str, Any]:
    """Insert many validated documents into a supported collection."""
    _ensure_worker_runtime()
    if not task_family_enabled("collection_writes"):
        return disabled_result("collection_writes")
    logger.info(
        "celery_insert_collection_documents_started task_id=%s collection=%s count=%s",
        self.request.id,
        collection,
        len(documents),
    )
    result = get_internal_ingest_service().insert_collection_documents(
        collection=collection,
        documents=documents,
        ignore_duplicates=ignore_duplicates,
    )
    return _serializable(result)


@celery_app.task(name="api.tasks.ingest.upsert_collection_document", bind=True)
def upsert_collection_document_task(
    self,
    *,
    collection: str,
    match: dict[str, Any],
    document: dict[str, Any],
    upsert: bool = False,
) -> dict[str, Any]:
    """Replace/update one validated document in a supported collection."""
    _ensure_worker_runtime()
    if not task_family_enabled("collection_writes"):
        return disabled_result("collection_writes")
    logger.info(
        "celery_upsert_collection_document_started task_id=%s collection=%s",
        self.request.id,
        collection,
    )
    result = get_internal_ingest_service().upsert_collection_document(
        collection=collection,
        match=match,
        document=document,
        upsert=upsert,
    )
    return _serializable(result)
