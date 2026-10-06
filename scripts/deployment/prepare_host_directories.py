#!/usr/bin/env python3
"""Prepare application storage from resolved Compose JSON without starting services."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path


def ensure_directory(path: Path, uid: int, gid: int) -> None:
    """Create missing directories and verify access for the container identity.

    Args:
        path: Absolute application-owned storage directory.
        uid: Numeric container user ID.
        gid: Numeric container primary group ID.

    Raises:
        OSError: Creation, ownership assignment, or container access fails.
        ValueError: The path is not absolute.

    Notes:
        Existing ownership and permissions are never changed. Only newly created
        directories are assigned to the container identity, when running as root.
    """
    if not path.is_absolute():
        raise ValueError(f"Storage path must be absolute: {path}")
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o750)
        if os.geteuid() == 0:
            os.chown(directory, uid, gid)
        print(f"[prepared] {directory}")
    for directory in (path, *path.parents):
        info = directory.stat()
        if not stat.S_ISDIR(info.st_mode):
            raise NotADirectoryError(str(directory))
        shift = 6 if info.st_uid == uid else 3 if info.st_gid == gid else 0
        required = 7 if directory == path else 1
        if uid != 0 and ((info.st_mode >> shift) & required) != required:
            raise PermissionError(
                f"Container {uid}:{gid} cannot access {directory}; prepare the path with "
                "the configured UID/GID using an authorized host administrator. "
                "Existing permissions were not changed."
            )


def prepare(config: dict) -> None:
    """Create writable application roots and runtime subdirectories from Compose.

    Args:
        config: Resolved Docker Compose configuration, including the API service.

    Raises:
        ValueError: API storage mounts or numeric container identity are missing.
        OSError: A required directory cannot be prepared or accessed.

    Notes:
        Does not create center configuration, pipeline input, MongoDB, or Docker
        volume directories. No database or Docker daemon operations are performed.
    """
    api = config.get("services", {}).get("api")
    if not api:
        raise ValueError("Resolved Compose configuration must include the API service")
    args = api.get("build", {}).get("args", {})
    identity = (
        api.get("user") or f"{args.get('COYOTE3_UID', 10001)}:{args.get('COYOTE3_GID', 10001)}"
    )
    parts = str(identity).split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("API container identity must use numeric UID:GID")
    uid, gid = map(int, parts)
    mounts = {
        volume["target"]: Path(volume["source"])
        for volume in api.get("volumes", [])
        if volume.get("type") == "bind" and not volume.get("read_only", False)
    }
    if not {"/data", "/app/logs"}.issubset(mounts):
        raise ValueError("API requires writable /data and /app/logs host mounts")
    label = api.get("environment", {}).get("ENV_NAME", "production")
    suffix = {
        "development": "dev",
        "production": "prod",
        "testing": "test",
        "staging": "stage",
    }.get(label, label)
    if suffix not in {"dev", "prod", "test", "stage"}:
        raise ValueError("Unsupported deployment environment")
    data = mounts["/data"]
    runtime = data / f"coyote3_{suffix}"
    for directory in (
        data,
        mounts["/app/logs"],
        runtime,
        runtime / "reports",
        runtime / "ingest_staging",
        runtime / "copied_sample_files" / "yaml",
    ):
        ensure_directory(directory, uid, gid)


def main() -> None:
    """Read resolved Compose JSON from stdin and prepare application storage."""
    try:
        prepare(json.load(sys.stdin))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: storage preparation failed: {exc}") from None


if __name__ == "__main__":
    main()
