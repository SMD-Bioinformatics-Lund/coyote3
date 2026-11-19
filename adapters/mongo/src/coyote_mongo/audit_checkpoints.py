# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Exclusive, durable checkpoint exports to an operator-provisioned archival mount."""

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def latest_checkpoint(
    directory: Path, *, max_age_seconds: float, now: datetime | None = None
) -> tuple[dict[str, Any], float]:
    """Read the newest export and reject missing, stale or invalid archive evidence.

    Freshness uses the archive file's modification time. This checks exporter
    liveness, not storage independence or retention enforcement. The caller must
    also verify the chain against an independently retained trusted checkpoint.
    """
    if not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
        raise ValueError("Checkpoint maximum age must be positive")
    if not directory.is_dir():
        raise ValueError("Checkpoint archive directory is unavailable")
    files = list(directory.glob("audit-*.json"))
    if not files:
        raise ValueError("No scheduled audit checkpoints are available")
    if any(path.is_symlink() for path in files):
        raise ValueError("Checkpoint must be a regular archive file")
    latest = max(files, key=lambda path: path.stat().st_mtime)
    if latest.is_symlink() or not latest.is_file():
        raise ValueError("Checkpoint must be a regular archive file")
    age = (now or datetime.now(timezone.utc)).timestamp() - latest.stat().st_mtime
    if age < -60 or age > max_age_seconds:
        raise ValueError("Scheduled audit checkpoint is stale or has a future timestamp")
    checkpoint = json.loads(latest.read_text())
    if not isinstance(checkpoint, dict) or checkpoint.get("valid") is not True:
        raise ValueError("Latest audit checkpoint is not a successful verification")
    return checkpoint, max(age, 0.0)


def archive_checkpoint(checkpoint: dict[str, Any], directory: Path) -> Path:
    """Create one checkpoint file without replacing any existing archive entry.

    Args:
        checkpoint: Successful audit-chain verification result containing hashes, not events.
        directory: Existing dedicated archive mount, provisioned outside the application.

    Returns:
        Path of the newly written, fsynced checkpoint.

    Raises:
        ValueError: Verification failed or the destination is not a directory.
        OSError: Exclusive creation, writing, synchronization or permission setting fails.

    Notes:
        Filesystem permissions are not WORM protection. The institution must independently
        enforce retention and prohibit deletion/overwrite on the archive storage.
    """
    if checkpoint.get("valid") is not True:
        raise ValueError("Failed audit verification cannot create a trusted checkpoint")
    if not directory.is_dir():
        raise ValueError("Checkpoint archive must be an existing dedicated directory")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"audit-{timestamp}-{uuid4().hex}.json"
    payload = json.dumps(checkpoint, sort_keys=True, indent=2).encode() + b"\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o440)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return path
