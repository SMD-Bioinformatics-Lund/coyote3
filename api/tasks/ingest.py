"""Celery tasks that execute validated internal ingest workflows."""

from __future__ import annotations

import os
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
from api.contracts.schemas.samples import SAMPLE_SOURCE_PATH_KEYS
from api.tasks.controls import disabled_result, task_family_enabled

logger = get_task_logger(__name__)
CONTAINER_DATA_ROOT = Path("/data")
WATCH_INGEST_LOCK_PATH = Path(
    os.getenv("COYOTE3_INGEST_WATCH_LOCK_PATH", "/tmp/coyote3_ingest_watch.lock")
)


def _ensure_worker_runtime() -> None:
    """Initialize runtime dependencies in the Celery worker process."""
    mode_flags = get_runtime_mode_flags()
    ensure_runtime_initialized(
        testing=mode_flags["testing"],
        development=mode_flags["development"],
    )


def _serializable(payload: Any) -> Any:
    return util.common.convert_to_serializable(payload)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


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


def _container_visible_path(path_value: str | os.PathLike[str]) -> Path:
    """Map center host data paths to the fixed container data mount."""
    path_obj = Path(path_value).expanduser()
    host_root = str(os.getenv("COYOTE3_DATA_HOST_ROOT", "")).strip()
    if not host_root or not path_obj.is_absolute():
        return path_obj
    host_root_path = Path(host_root).expanduser()
    try:
        relative = path_obj.relative_to(host_root_path)
    except ValueError:
        return path_obj
    return CONTAINER_DATA_ROOT / relative


def _translate_payload_source_path(value: Any, manifest_path: Path) -> Any:
    """Resolve relative paths and map configured host-root paths to /data."""
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
    return str(_container_visible_path(path_value))


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
    raw_watch_dir = str(os.getenv("COYOTE3_INGEST_WATCH_DIR", "")).strip()
    if not raw_watch_dir:
        return {"status": "disabled", "reason": "COYOTE3_INGEST_WATCH_DIR is not configured"}

    watch_dir = _container_visible_path(raw_watch_dir)
    if not watch_dir.exists():
        return {"status": "not_found", "watch_dir": str(watch_dir), "scanned": 0}
    if not watch_dir.is_dir():
        return {"status": "invalid", "watch_dir": str(watch_dir), "reason": "not a directory"}

    manifest_name = os.getenv("COYOTE3_INGEST_WATCH_FILENAME", "coyote3.yaml")
    done_suffix = os.getenv("COYOTE3_INGEST_DONE_SUFFIX", ".done")
    failed_suffix = os.getenv("COYOTE3_INGEST_FAILED_SUFFIX", ".failed")
    allow_update = _truthy(os.getenv("COYOTE3_INGEST_WATCH_UPDATE_EXISTING", "0"))
    increment = _truthy(os.getenv("COYOTE3_INGEST_WATCH_INCREMENT", "0"))

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
    if not task_family_enabled("ingest_watch"):
        return disabled_result("ingest_watch")
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
    if not task_family_enabled("ingest_bundle"):
        return disabled_result("ingest_bundle")
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
            metadata={"task_id": self.request.id, "counts": result.get("counts")},
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


@celery_app.task(name="api.tasks.ingest.ingest_dependents", bind=True)
def ingest_dependents_task(
    self,
    *,
    sample_id: str,
    sample_name: str,
    delete_existing: bool,
    preload: dict[str, Any],
) -> dict[str, Any]:
    """Write dependent analysis documents for an existing sample."""
    _ensure_worker_runtime()
    if not task_family_enabled("ingest_dependents"):
        return disabled_result("ingest_dependents")
    logger.info(
        "celery_ingest_dependents_started task_id=%s sample_id=%s", self.request.id, sample_id
    )
    written = get_internal_ingest_service().ingest_dependents(
        sample_id=sample_id,
        sample_name=sample_name,
        delete_existing=delete_existing,
        preload=preload,
    )
    return _serializable({"status": "ok", "sample_id": sample_id, "written": written})


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
