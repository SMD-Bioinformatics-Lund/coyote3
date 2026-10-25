"""Exclusive, durable checkpoint exports to an operator-provisioned archival mount."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


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
