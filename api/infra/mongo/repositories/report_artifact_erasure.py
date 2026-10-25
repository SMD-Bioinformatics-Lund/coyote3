"""Durable removal of generated report files after committed sample deletion."""

import logging
import os
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.config.operational_collections import OPERATIONAL_COLLECTIONS
from api.infra.mongo.repositories.audit_outbox import audit_route, enqueue_audit
from api.infra.mongo.transactions import run_transaction
from coyote3.domain.exceptions import AppError

logger = logging.getLogger(__name__)


def enqueue_report_erasure(
    reports: Any,
    selector: dict[str, Any],
    *,
    root: str | Path,
    sample_id: str,
    session: Any,
) -> int:
    """Capture owned HTML/PDF paths in the same transaction as sample deletion.

    Args:
        reports: Primary report collection containing the soon-to-be-deleted records.
        selector: Exact sample ownership predicate.
        root: Configured generated-report directory.
        sample_id: Deleted sample's internal identifier for audit correlation.
        session: Owning sample deletion transaction.

    Returns:
        Number of distinct artifact paths queued, including already-missing files.

    Raises:
        AppError: A path escapes the report root, has an unexpected suffix, or is shared.
    """
    base = Path(root).resolve()
    documents = list(
        reports.find(selector, {"filepath": 1, "pdf_filepath": 1, "artifacts": 1}, session=session)
    )
    paths = {
        str(document[field])
        for document in documents
        for field in ("filepath", "pdf_filepath")
        if document.get(field)
    }
    paths.update(
        artifact["staging_path"]
        for document in documents
        for artifact in document.get("artifacts", [])
        if artifact.get("staging_path")
    )
    queue = reports.database[OPERATIONAL_COLLECTIONS.report_artifact_erasure]
    if paths and not base.is_dir():
        raise AppError(409, "Report storage must be available before sample deletion.")
    for path in sorted(paths):
        absolute = Path(path)
        if (
            not absolute.is_absolute()
            or ".." in absolute.parts
            or not absolute.is_relative_to(base)
            or not _report_artifact_path(absolute)
            or not absolute.resolve().is_relative_to(base)
        ):
            raise AppError(409, "Report artifact requires reconciliation before sample deletion.")
        if reports.find_one(
            {
                "$and": [
                    {"$nor": [selector]},
                    {
                        "$or": [
                            {"filepath": path},
                            {"pdf_filepath": path},
                            {"artifacts.staging_path": path},
                        ]
                    },
                ]
            },
            {"_id": 1},
            session=session,
        ):
            raise AppError(409, "Report artifact is referenced by another sample.")
        queue.insert_one(
            {
                "sample_id": sample_id,
                "route": audit_route(os.environ),
                "root": str(base),
                "root_device": base.stat().st_dev,
                "root_inode": base.stat().st_ino,
                "path": str(absolute.relative_to(base)),
                "source_path": path,
                "created_at": datetime.now(timezone.utc),
            },
            session=session,
        )
    return len(paths)


def _report_artifact_path(path: Path) -> bool:
    """Recognize final and staged report filenames eligible for owned-file erasure."""
    return path.name.lower().endswith((".html", ".pdf", ".html.pending", ".pdf.pending"))


def _unlink_report(root: Path, relative: str) -> None:
    """Unlink one directory entry without traversing symlinked parent directories.

    Missing files are already erased. Directory descriptors prevent path replacement
    from redirecting traversal outside the configured root. Only the final entry is
    unlinked; a final symlink's target is never followed.
    """
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not _report_artifact_path(path):
        raise ValueError("Invalid queued report path")
    try:
        with ExitStack() as stack:
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, directory)
            for component in path.parts[:-1]:
                directory = os.open(
                    component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                )
                stack.callback(os.close, directory)
            os.unlink(path.name, dir_fd=directory)
    except FileNotFoundError:
        return


def erase_pending_reports(reports: Any, *, root: str | Path, limit: int = 100) -> dict[str, int]:
    """Retry committed erasures, retaining failed jobs and recording successful completion.

    Args:
        reports: Primary report collection used to check remaining references.
        root: Current configured report directory; must match the queued root.
        limit: Maximum pending file jobs attempted per invocation.

    Returns:
        Completed and pending-on-error counts for attempted jobs. Paths are not logged.
    """
    base = Path(root).resolve()
    queue = reports.database[OPERATIONAL_COLLECTIONS.report_artifact_erasure]
    completed = failed = 0
    for job in queue.find({"route": audit_route(os.environ)}).sort("last_attempt", 1).limit(limit):
        reason = "io_error"
        try:
            if not base.is_dir():
                reason = "storage_unavailable"
                raise OSError("Configured report directory is unavailable")
            if job["root"] != str(base):
                reason = "root_changed"
                raise ValueError("Configured report root changed")
            if (job["root_device"], job["root_inode"]) != (base.stat().st_dev, base.stat().st_ino):
                reason = "storage_identity_changed"
                raise ValueError("Report storage identity changed")
            if reports.find_one(
                {
                    "$or": [
                        {"filepath": job["source_path"]},
                        {"pdf_filepath": job["source_path"]},
                    ]
                },
                {"_id": 1},
            ):
                reason = "still_referenced"
                raise ValueError("Report path is still referenced")
            _unlink_report(base, job["path"])

            def finish(session: Any) -> None:
                """Acknowledge the file job and its audit receipt atomically."""
                if queue.find_one_and_delete({"_id": job["_id"]}, session=session):
                    enqueue_audit(
                        reports.database,
                        session,
                        event_type="sample.report_artifact_erased",
                        resource_type="sample",
                        resource_id=job["sample_id"],
                        metadata={"artifact_count": 1},
                    )

            run_transaction(reports.database.client, finish)
            completed += 1
        except (OSError, ValueError) as exc:
            if isinstance(exc, PermissionError):
                reason = "permission_denied"
            elif isinstance(exc, ValueError) and reason == "io_error":
                reason = "invalid_path"
            queue.update_one(
                {"_id": job["_id"]},
                {
                    "$set": {
                        "last_attempt": datetime.now(timezone.utc),
                        "status": "retry_required",
                        "last_error": reason,
                    },
                    "$inc": {"attempts": 1},
                },
            )
            logger.warning("Report artifact erasure deferred: reason=%s job=%s", reason, job["_id"])
            failed += 1
    return {
        "completed": completed,
        "retry_required": failed,
        **report_erasure_backlog(reports.database),
    }


def report_erasure_backlog(database: Any) -> dict[str, int]:
    """Measure this deployment's pending erasures without exposing artifact paths.

    Args:
        database: Application database that owns the committed erasure queue.

    Returns:
        Pending job count, jobs requiring retry and oldest job age in seconds.
        An empty queue has zero age. Reads never bypass mount or ownership checks.
    """
    queue = database[OPERATIONAL_COLLECTIONS.report_artifact_erasure]
    selector = {"route": audit_route(os.environ)}
    oldest = queue.find_one(selector, {"created_at": 1}, sort=[("created_at", 1)])
    age = 0
    if oldest and isinstance(oldest.get("created_at"), datetime):
        created = oldest["created_at"]
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = max(0, int((datetime.now(timezone.utc) - created).total_seconds()))
    return {
        "pending": queue.count_documents(selector),
        "oldest_age_seconds": age,
        "failed_pending": queue.count_documents({**selector, "status": "retry_required"}),
    }
