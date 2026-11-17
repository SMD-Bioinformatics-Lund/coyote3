#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Build core, server, HTTP client and ingestion wheels from isolated source trees."""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build_sdk(output_directory: Path, *, build_isolation: bool = True) -> None:
    """Build the selected application distributions without stale generated sources.

    Args:
        output_directory: Destination for the built wheels, created if absent.
        build_isolation: Install build dependencies in pip's isolated environment.
            False uses build tools already installed in the invoking environment.

    Raises:
        OSError: Sources cannot be staged or the destination cannot be created.
        subprocess.CalledProcessError: Pip cannot build the staged project.
    """
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    for project in (
        ROOT / "core",
        ROOT,
        ROOT / "clients/python",
        ROOT / "services/relay",
        ROOT / "services/atlas",
        ROOT / "services/demo",
    ):
        with tempfile.TemporaryDirectory(prefix="coyote-package-build-") as temporary:
            staging = Path(temporary)
            for name in ("pyproject.toml", "LICENSE.txt", "COPYRIGHT.txt", "NOTICE.txt"):
                shutil.copyfile(project / name, staging / name)
            for name in (
                "README.md",
                "CONTRIBUTING.md",
                "MANIFEST.in",
                "build_support.py",
                "package_build.py",
                "client_build.py",
                "relay_build.py",
                "demo_build.py",
                "LICENSING.md",
                "THIRD_PARTY_NOTICES.md",
                "CHANGELOG.md",
            ):
                if (project / name).is_file():
                    shutil.copyfile(project / name, staging / name)
            if project == ROOT:
                sources = (
                    "api/src",
                    "api/docs",
                    "api/tests",
                    "adapters/mongo/src",
                    "adapters/mongo/docs",
                    "adapters/mongo/tests",
                )
                for component in ("api", "adapters/mongo"):
                    (staging / component).mkdir(parents=True, exist_ok=True)
                    for name in (
                        "README.md",
                        "CHANGELOG.md",
                        "pyproject.toml",
                        "LICENSE.txt",
                        "COPYRIGHT.txt",
                        "NOTICE.txt",
                    ):
                        shutil.copyfile(project / component / name, staging / component / name)
            else:
                sources = ("src", "docs", "tests")
            for name in sources:
                source = project / name
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.is_file():
                    shutil.copyfile(source, target)
                else:
                    shutil.copytree(
                        source,
                        target,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
                    )
            command = [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--wheel-dir",
                str(output_directory),
            ]
            if not build_isolation:
                command.append("--no-build-isolation")
            subprocess.run([*command, str(staging)], check=True)


def main() -> None:
    """Build the selected core, server, client and ingestion distributions for deployment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--no-build-isolation", action="store_true")
    args = parser.parse_args()
    build_sdk(args.output_dir, build_isolation=not args.no_build_isolation)


if __name__ == "__main__":
    main()
