# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Stable manifest discovery and acknowledgement for durable ingestion hosts."""

from __future__ import annotations

import logging
from collections.abc import Callable
from hashlib import sha256
from os import stat_result
from pathlib import Path
from typing import Any

from coyote_contracts.manifests import ALL_MANIFEST_FILE_KEYS
from pydantic import BaseModel, ConfigDict

from coyote.application.common.observability import timed_operation
from coyote.application.ingest.failures import ingest_failure_message

logger = logging.getLogger(__name__)


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
    """Resolve a declared input path relative to the manifest directory.

    Args:
        value: Path scalar or source metadata mapping containing a path key.
        manifest_path: Local manifest whose directory owns relative inputs.

    Returns:
        Absolute path text, or copied metadata with its nonempty path resolved.
        Other metadata keys and empty mapping paths remain unchanged.
    """
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


def resolve_relative_sample_paths(payload: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    """Resolve supported manifest input paths against the manifest's directory.

    Args:
        payload: Parsed manifest, including top-level and nested files declarations.
        manifest_path: Local manifest whose directory owns relative paths.

    Returns:
        A copied manifest with declared source paths resolved. Unrecognized keys,
        empty inputs and non-path metadata retain their original values.
    """
    resolved = dict(payload)
    for key in ALL_MANIFEST_FILE_KEYS:
        if resolved.get(key):
            resolved[key] = _translate_payload_source_path(resolved[key], manifest_path)
    files = resolved.get("files")
    if isinstance(files, dict):
        resolved["files"] = {
            key: _translate_payload_source_path(value, manifest_path)
            if key in ALL_MANIFEST_FILE_KEYS and value
            else value
            for key, value in files.items()
        }
    return resolved


def _manifest_unchanged(path: Path, expected: stat_result | None) -> bool:
    """Check that a watched manifest still matches the file read by this scan.

    Args:
        path: Manifest awaiting acknowledgement.
        expected: File metadata captured before reading, or None if reading failed.

    Returns:
        False for an unread, missing, inaccessible, replaced, or modified manifest.

    Notes:
        This detects changes during processing, not concurrent writes between
        this check and rename. Producers must not modify a submitted manifest.
    """
    if expected is None:
        return False
    try:
        current = path.stat()
    except OSError:
        return False
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    return all(getattr(current, field) == getattr(expected, field) for field in fields)


class ManifestWatchSettings(BaseModel):
    """Explicit scan paths and submission behavior selected by the host."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    directory: Path
    manifest_name: str
    done_suffix: str
    failed_suffix: str
    update_existing: bool
    increment: bool


class ManifestWatcher:
    """Discover immutable manifests and acknowledge only completed durable jobs.

    The host owns scan locking. Parsing, submission, execution, retry classification
    and audit callbacks make this workflow independent of a broker and database.
    """

    def __init__(
        self,
        *,
        settings: ManifestWatchSettings,
        parse_payload: Callable[[str], dict[str, Any]],
        submit_job: Callable[..., str],
        execute_job: Callable[[str], dict[str, Any]],
        retryable_error: Callable[[Exception], bool],
        audit: Callable[..., None],
        observer: Callable[..., None] | None = None,
    ) -> None:
        """Bind the host's scan configuration and ingestion ports.

        Args:
            settings: Immutable scan paths, suffixes and ingestion options.
            parse_payload: Validate manifest text using the clinical ingestion contract.
            submit_job: Retain a durable job before execution.
            execute_job: Execute or recover a previously retained job.
            retryable_error: Classify failures that must leave a manifest for retry.
            audit: Best-effort manifest acknowledgement traceability.
            observer: Optional operation timing observer.
        """
        self.settings = settings
        self.parse_payload = parse_payload
        self.submit_job = submit_job
        self.execute_job = execute_job
        self.retryable_error = retryable_error
        self.audit = audit
        self.observer = observer

    def scan(self, *, task_id: str | None = None) -> dict[str, Any]:
        """Discover stable manifests and execute their durable ingest jobs.

        Args:
            task_id: Optional scan identifier for audit metadata and marker collisions.

        Returns:
            Directory status, or scan counts and successful/failed acknowledgements.

        Notes:
            Uses the supplied task ID for tracing and marker names. The caller
            owns the scan lock. Jobs are submitted before execution; changed manifests
            and retryable failures remain for a later scan. Busy or disabled jobs are
            skipped without a completion marker or success audit, preserving their
            manifests for later processing. An acknowledgement failure does not undo
            committed data. Nonretryable failures receive a failure marker when
            directory permissions allow it.
        """
        watch_dir = self.settings.directory
        if not watch_dir.exists():
            return {"status": "not_found", "watch_dir": str(watch_dir), "scanned": 0}
        if not watch_dir.is_dir():
            return {"status": "invalid", "watch_dir": str(watch_dir), "reason": "not a directory"}

        manifest_name = self.settings.manifest_name
        done_suffix = self.settings.done_suffix
        failed_suffix = self.settings.failed_suffix
        allow_update = self.settings.update_existing
        increment = self.settings.increment

        manifests = sorted(path for path in watch_dir.rglob(manifest_name) if path.is_file())
        ingested: list[dict[str, Any]] = []
        failed: list[dict[str, str]] = []

        for manifest_path in manifests:
            before = None
            try:
                task_context = {"task_id": task_id, "manifest": str(manifest_path)}
                with timed_operation(
                    "ingest.manifest_parse", observer=self.observer, **task_context
                ):
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
                    payload = self.parse_payload(manifest_bytes.decode("utf-8"))
                    payload = resolve_relative_sample_paths(payload, manifest_path)
                with timed_operation(
                    "ingest.sample_bundle", observer=self.observer, **task_context
                ):
                    identity = sha256(
                        f"{manifest_path.resolve()}:{after.st_mtime_ns}:".encode() + manifest_bytes
                    ).hexdigest()
                    self.submit_job(
                        job_id=identity,
                        source_payload=payload,
                        update_existing=allow_update,
                        increment=increment,
                        submitted_by="ingest-watcher",
                    )
                    result = self.execute_job(identity)
                    if result.get("status") in {"busy", "disabled"}:
                        continue
                if not _manifest_unchanged(manifest_path, before):
                    logger.warning("Manifest changed during ingest; acknowledgement deferred")
                    continue
                done_path = _unique_marker_path(manifest_path, done_suffix, task_id)
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
                self.audit(
                    "ingest.watch.succeeded",
                    "Watched manifest ingested",
                    resource_type="sample",
                    resource_id=str(result.get("sample_id", "")),
                    resource_name=str(result.get("sample_name", "")),
                    metadata={
                        "manifest": str(manifest_path),
                        "done_path": str(done_path),
                        "task_id": task_id,
                        "counts": result.get("counts") or result.get("data_counts"),
                    },
                )
            except Exception as exc:
                logger.exception("celery_ingest_watch_failed manifest=%s", manifest_path)
                if self.retryable_error(exc):
                    continue
                if not _manifest_unchanged(manifest_path, before):
                    logger.warning("Manifest changed during ingest; failure marker deferred")
                    continue
                failed_path = _unique_marker_path(manifest_path, failed_suffix, task_id)
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
                self.audit(
                    "ingest.watch.failed",
                    f"Watched manifest ingest failed: {ingest_failure_message(exc, retryable=False)}",
                    severity="error",
                    outcome="failure",
                    resource_type="manifest",
                    resource_id=str(manifest_path),
                    metadata={
                        "manifest": str(manifest_path),
                        "failed_path": marker_path,
                        "task_id": task_id,
                        "error": str(exc),
                    },
                )

        return {
            "status": "ok",
            "watch_dir": str(watch_dir),
            "manifest": manifest_name,
            "scanned": len(manifests),
            "ingested": ingested,
            "failed": failed,
        }
