#!/usr/bin/env python3
"""Build core and server from isolated sources so stale build files cannot enter a wheel."""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build_sdk(output_directory: Path, *, build_isolation: bool = True) -> None:
    """Stage distribution inputs and build a wheel in a fresh temporary directory.

    Args:
        output_directory: Destination for the built wheel, created if absent.
        build_isolation: Install build dependencies in pip's isolated environment.
            False uses build tools already installed in the invoking environment.

    Raises:
        OSError: Sources cannot be staged or the destination cannot be created.
        subprocess.CalledProcessError: Pip cannot build the staged project.
    """
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="coyote3-sdk-build-") as temporary:
        staging = Path(temporary)
        for name in (
            "pyproject.toml",
            "README.md",
            "LICENSE.txt",
            "NOTICE.txt",
            "LICENSING.md",
            "THIRD_PARTY_NOTICES.md",
            "release.toml",
            "build_support.py",
            "MANIFEST.in",
        ):
            shutil.copyfile(ROOT / name, staging / name)
        shutil.copytree(
            ROOT / "src/coyote3",
            staging / "src/coyote3",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
        )
        for name in ("api", "config/examples/center", "demo_data/clinical_workflows"):
            shutil.copytree(
                ROOT / name,
                staging / name,
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
    """Build a release wheel from explicitly staged core, server and resource inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--no-build-isolation", action="store_true")
    args = parser.parse_args()
    build_sdk(args.output_dir, build_isolation=not args.no_build_isolation)


if __name__ == "__main__":
    main()
