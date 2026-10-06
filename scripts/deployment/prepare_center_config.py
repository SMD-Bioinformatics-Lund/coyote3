#!/usr/bin/env python3
"""Stage and validate a center configuration release from local files or pinned Git."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

FILES = (
    "contact.toml",
    "clinical_vocabulary.toml",
    "clinical_query_policy.toml",
    "filter_flag_metadata.yaml",
)
ROOT = Path(__file__).resolve().parents[2]


def prepare(source: str, destination: Path, revision: str | None, subdirectory: str) -> None:
    """Publish a validated configuration directory without overwriting an existing release.

    Args:
        source: Local directory or Git repository URL. HTTP credentials are forbidden.
        destination: New directory outside the application checkout, created on success.
        revision: Full 40-character Git commit ID; required for repository URLs.
        subdirectory: Relative repository directory containing the four configuration files.

    Raises:
        ValueError: Source options are unsafe, missing, or incompatible.
        FileExistsError: The destination already exists.
        OSError: A file or Git command cannot be accessed.
        subprocess.CalledProcessError: Fetching or application validation fails.

    Notes:
        Fetches configuration as data only. No repository scripts are executed.
        Application validation runs without database access. Failed validation never
        replaces the destination; application upgrades never invoke this command.
    """
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    if destination.is_relative_to(ROOT):
        raise ValueError("Center configuration must live outside the application checkout")
    directory = PurePosixPath(subdirectory)
    if directory.is_absolute() or ".." in directory.parts:
        raise ValueError("Git subdirectory must be a relative path without parent traversal")
    local = Path(source).expanduser()
    is_local = local.is_dir()
    if is_local and revision:
        raise ValueError("Use a repository URL for a pinned revision, or a local directory")
    if not is_local:
        if not revision or not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
            raise ValueError("Git sources require a full 40-character commit ID")
        parsed = urlsplit(source)
        if not (parsed.scheme in {"https", "ssh"} or source.startswith("git@")):
            raise ValueError("Git source must use HTTPS or SSH")
        if parsed.password or (parsed.scheme == "https" and parsed.username):
            raise ValueError("Use a credential helper or SSH agent, not credentials in URLs")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".center-config-", dir=destination.parent) as temp:
        staging = Path(temp) / "release"
        staging.mkdir()
        if is_local:
            for name in FILES:
                shutil.copyfile(local / name, staging / name)
        else:
            repository = Path(temp) / "repository"
            subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "fetch", "--quiet", "--depth=1", source, revision],
                check=True,
            )
            for name in FILES:
                content = subprocess.check_output(
                    ["git", "-C", str(repository), "show", f"{revision}:{directory / name}"]
                )
                (staging / name).write_bytes(content)
        env = dict(os.environ, COYOTE3_CENTER_CONFIG_DIR=str(staging), PYTHONPATH=str(ROOT))
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from api.config.clinical_query_policy import load_clinical_query_policy; "
                    "from api.config.loaders.filter_flags import load_filter_flag_metadata; "
                    "from api.config.loaders.contact import load_contact_config; "
                    "from api.config.paths import CONTACT_CONFIG_PATH; "
                    "load_clinical_query_policy(); load_filter_flag_metadata(); "
                    "load_contact_config(CONTACT_CONFIG_PATH, organization_name='Validation', "
                    "public_base_url='', script_name='')"
                ),
            ],
            env=env,
            cwd=ROOT,
            check=True,
        )
        manifest = {
            "format": 1,
            "source": source,
            "revision": revision,
            "subdirectory": None if is_local else str(directory),
            "sha256": {
                name: hashlib.sha256((staging / name).read_bytes()).hexdigest() for name in FILES
            },
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        for file in staging.iterdir():
            file.chmod(0o644)
        staging.chmod(0o755)
        staging.rename(destination)


def main() -> None:
    """Parse a configuration source and publish one validated center release."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Local directory or Git repository URL")
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--revision", help="Full Git commit SHA; required for a repository URL")
    parser.add_argument("--subdirectory", default=".")
    args = parser.parse_args()
    prepare(args.source, args.destination, args.revision, args.subdirectory)
    print(f"Validated center configuration: {args.destination}")


if __name__ == "__main__":
    main()
