"""Publish committed report artifacts with repeatable, checksum-verified file operations."""

import os
from hashlib import sha256
from pathlib import Path
from typing import Any


def finalize_artifacts(artifacts: list[dict[str, Any]], *, root: str | Path) -> None:
    """Publish staged files without replacing existing content.

    Args:
        artifacts: Committed artifact paths, staging paths and SHA-256 checksums.
        root: Allowed report-storage directory.

    Raises:
        ValueError: A path escapes storage or existing content fails verification.
        OSError: Storage is unavailable; a later invocation can resume publication.
    """
    base = Path(root).resolve(strict=True)
    for artifact in artifacts:
        destination = Path(artifact["path"])
        staging = Path(artifact["staging_path"])
        for path in (destination, staging):
            if path.is_symlink() or not path.resolve().is_relative_to(base):
                raise ValueError("Report artifact path is outside its storage directory")
        if staging != Path(str(destination) + ".pending"):
            raise ValueError("Unexpected report staging path")
        if destination.suffix not in {".html", ".pdf"}:
            raise ValueError("Unexpected report artifact format")
        checksum = artifact["checksum"]
        if not destination.exists():
            if sha256(staging.read_bytes()).hexdigest() != checksum:
                raise ValueError("Staged report artifact failed checksum verification")
            try:
                os.link(staging, destination)
            except FileExistsError:
                pass
        if sha256(destination.read_bytes()).hexdigest() != checksum:
            raise ValueError("Published report artifact failed checksum verification")
        directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
            staging.unlink(missing_ok=True)
            os.fsync(directory)
        finally:
            os.close(directory)


def discard_deleted_report_artifacts(artifacts: list[dict[str, Any]]) -> None:
    """Remove verified files when their report was deleted during publication.

    Args:
        artifacts: Previously path-validated report artifacts with their content checksums.

    Raises:
        OSError: Storage is unavailable; the deletion queue also retains these paths.
    """
    for artifact in artifacts:
        for key in ("path", "staging_path"):
            path = Path(artifact[key])
            if path.is_file() and not path.is_symlink():
                if sha256(path.read_bytes()).hexdigest() == artifact["checksum"]:
                    path.unlink(missing_ok=True)


def finalize_pending_reports(repository: Any, *, root: str | Path) -> dict[str, int]:
    """Retry publication for at most 100 reports without changing clinical content.

    Args:
        repository: Report repository exposing pending artifacts and completion updates.
        root: Configured report-storage directory.

    Returns:
        Completed and deferred counts; damaged or unavailable files remain pending.
    """
    result = {"completed": 0, "deferred": 0}
    for report in repository.pending_artifacts(limit=100):
        try:
            finalize_artifacts(report["artifacts"], root=root)
            if repository.complete_artifacts(report["_id"]):
                result["completed"] += 1
            else:
                discard_deleted_report_artifacts(report["artifacts"])
        except (OSError, ValueError):
            result["deferred"] += 1
    return result
