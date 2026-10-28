#!/usr/bin/env python3
"""Prepare application storage from resolved Compose JSON without starting services."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import tomllib
from pathlib import Path


def prepare_accreditation_logo(directory: Path) -> None:
    """Copy an absolute host logo into the mounted center and rewrite its setting.

    Args:
        directory: Existing host directory mounted as the container's center configuration.

    Raises:
        OSError: The source cannot be read or the center directory cannot be written.
        ValueError: The logo type, destination, or contact setting is invalid.

    Notes:
        Relative paths and empty settings remain unchanged. Content-addressed copies
        preserve existing assets. The contact file is replaced atomically only after
        the logo is copied; the original source image is never modified.
    """
    contact = directory / "contact.toml"
    text = contact.read_text()
    document = tomllib.loads(text)
    value = document.get("organization", {}).get("accreditation_logo", "")
    if not isinstance(value, str) or not Path(value).is_absolute():
        return
    source = Path(value)
    suffix = source.suffix.lower()
    if suffix not in {".svg", ".png", ".jpg", ".jpeg"}:
        raise ValueError("Accreditation logo must be SVG, PNG, or JPEG")
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    relative = f"logos/accreditation-{digest}{suffix}"
    # Keep surrounding contact settings and comments intact; validate the entire
    # rewritten document before publishing to catch unsupported TOML layouts.
    section = re.search(r"(?m)^\[organization\][ \t]*(?:#[^\n]*)?$", text)
    if section is None:
        raise ValueError("Absolute accreditation_logo requires an [organization] table")
    end = re.search(r"(?m)^\s*\[", text[section.end() :])
    stop = section.end() + end.start() if end else len(text)
    block = text[section.end() : stop]
    updated, count = re.subn(
        r"""(?m)^(\s*accreditation_logo\s*=\s*)(?:"[^"\n]*"|'[^'\n]*')([ \t]*(?:#[^\n]*)?)$""",
        lambda match: match[1] + json.dumps(relative) + match[2],
        block,
    )
    replacement = text[: section.end()] + updated + text[stop:]
    document["organization"]["accreditation_logo"] = relative
    if count != 1 or tomllib.loads(replacement) != document:
        raise ValueError("Use a single-line accreditation_logo string in [organization]")
    manifest_path = directory / "manifest.json"
    manifest = None
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        if not isinstance(manifest, dict) or not isinstance(manifest.get("sha256"), dict):
            raise ValueError("Center manifest must contain a sha256 mapping")
        manifest["sha256"]["contact.toml"] = hashlib.sha256(replacement.encode()).hexdigest()
        manifest["sha256"][relative] = digest
    logos = directory / "logos"
    if logos.is_symlink():
        raise ValueError("Center logos directory must not be a symbolic link")
    logos.mkdir(mode=0o755, exist_ok=True)
    target = directory / relative
    if target.is_symlink():
        raise ValueError("Accreditation logo destination must not be a symbolic link")
    if target.exists():
        if target.read_bytes() != content:
            raise ValueError("Existing accreditation logo copy has unexpected contents")
    else:
        with target.open("xb") as stream:
            stream.write(content)
        target.chmod(0o644)
    with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(replacement)
            stream.flush()
            temporary.chmod(stat.S_IMODE(contact.stat().st_mode))
            temporary.replace(contact)
        finally:
            temporary.unlink(missing_ok=True)
    if manifest is not None:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("[prepared] Center accreditation logo and container-relative contact setting")


def check_directory_access(path: Path, uid: int, gid: int, *, mount_root: Path) -> None:
    """Check container access inside a bind mount without inspecting host-only parents.

    Args:
        path: Existing directory exposed inside the container.
        uid: Container user ID; zero bypasses discretionary mode checks.
        gid: Container primary group ID.
        mount_root: Host source of the bind mount containing the directory.

    Raises:
        ValueError: The directory is outside its declared mount.
        OSError: A directory is absent, is a file, or lacks required mode bits.

    Notes:
        Host ancestors above the bind source are not traversed by container
        processes. No directories or permissions are changed by this check.
    """
    if not path.is_relative_to(mount_root):
        raise ValueError("Storage directory must be inside its bind mount")
    directories = [path]
    current = path
    while current != mount_root:
        current = current.parent
        directories.append(current)
    for directory in directories:
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


def ensure_directory(path: Path, uid: int, gid: int, *, mount_root: Path | None = None) -> None:
    """Create missing directories and verify access for the container identity.

    Args:
        path: Absolute application-owned storage directory.
        uid: Numeric container user ID.
        gid: Numeric container primary group ID.
        mount_root: Bind source whose container-visible ancestors must be checked;
            defaults to the requested directory itself.

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
    check_directory_access(path, uid, gid, mount_root=mount_root or path)


def prepare(config: dict) -> None:
    """Create writable application roots and runtime subdirectories from Compose.

    Args:
        config: Resolved Docker Compose configuration, including the API service.

    Raises:
        ValueError: API storage mounts or numeric container identity are missing.
        OSError: A required directory cannot be prepared or accessed.

    Notes:
        Imports an absolute accreditation logo into an existing center mount.
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
        root = data if directory.is_relative_to(data) else mounts["/app/logs"]
        ensure_directory(directory, uid, gid, mount_root=root)
    centers = {
        Path(volume["source"])
        for service in config.get("services", {}).values()
        for volume in service.get("volumes", [])
        if volume.get("type") == "bind" and volume.get("target") == "/app/center-config"
    }
    for center in sorted(centers):
        prepare_accreditation_logo(center)


def main() -> None:
    """Read resolved Compose JSON and prepare storage and center accreditation artwork."""
    try:
        prepare(json.load(sys.stdin))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: host preparation failed: {exc}") from None


if __name__ == "__main__":
    main()
