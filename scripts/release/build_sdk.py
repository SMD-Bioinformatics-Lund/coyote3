#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Build application wheels and retain pinned external package artifacts."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL_DISTRIBUTIONS = {
    "coyote-contracts": "contracts_version",
    "coyote-relay": "relay_version",
}


class ExternalArtifact:
    """Stage a pinned external package wheel without passing credentials into images."""

    def __init__(self, root: Path, distribution: str, directory: Path | None = None) -> None:
        """Read the reviewed Git source and selected version from application metadata."""
        self.root = root
        self.distribution = distribution
        version_field = EXTERNAL_DISTRIBUTIONS[distribution]
        metadata = tomllib.loads((root / "pyproject.toml").read_text())
        self.source = metadata["tool"]["uv"]["sources"][distribution]
        if not isinstance(self.source, dict) or not all(
            isinstance(value, str) for value in self.source.values()
        ):
            raise ValueError("The external package requires a Git source with a full commit")
        url = urlsplit(self.source.get("git", ""))
        if (
            set(self.source) != {"git", "rev"}
            or url.scheme != "https"
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or re.fullmatch(r"[0-9a-f]{40}", self.source.get("rev", "")) is None
        ):
            raise ValueError(
                "The external package requires a credential-free HTTPS Git URL and full commit"
            )
        self.version = tomllib.loads((root / "release.toml").read_text())[version_field]
        self.directory = directory or root / ".release" / distribution.removeprefix("coyote-")

    def _validate_wheel(self, wheel: Path) -> None:
        """Reject artifacts that do not identify the selected package distribution."""
        with zipfile.ZipFile(wheel) as archive:
            names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                raise ValueError("External wheel must contain exactly one package metadata record")
            metadata = Parser().parsestr(archive.read(names[0]).decode())
            if metadata["Name"] != self.distribution or metadata["Version"] != self.version:
                raise ValueError("External wheel differs from the selected distribution or version")

    def validate(self) -> Path:
        """Require the cached wheel to match the selected source, version and checksum.

        Returns:
            Verified wheel path.

        Raises:
            OSError: The prepared artifact is missing or unreadable.
            ValueError: Its source, identity, record or checksum differs from the selection.
        """
        record = json.loads((self.directory / "artifact.json").read_text())
        if not isinstance(record, dict):
            raise ValueError("Prepared external package metadata must be an object")
        if record.get("source") != self.source or record.get("version") != self.version:
            raise ValueError(
                "Prepared external package source differs from the application selection"
            )
        filename = record.get("filename", "")
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or not filename.endswith(".whl")
        ):
            raise ValueError("Prepared external package must identify one wheel filename")
        wheel = self.directory / filename
        if wheel.is_symlink():
            raise ValueError("Prepared package wheel must be a regular file")
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != record.get("sha256"):
            raise ValueError("Prepared package wheel checksum differs")
        self._validate_wheel(wheel)
        return wheel

    def prepare(self, *, build_isolation: bool = True) -> Path:
        """Build the exact Git revision with the host's existing credential helper.

        Args:
            build_isolation: Install build requirements in an isolated environment.

        Returns:
            Validated cached wheel; a matching cache requires no network connection.

        Raises:
            ValueError: Git source metadata or the resulting wheel is invalid.
            OSError: Local build storage cannot be read or written.
            subprocess.CalledProcessError: Authentication, fetching or wheel building fails.
        """
        try:
            return self.validate()
        except (OSError, ValueError, zipfile.BadZipFile):
            pass
        self.directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.directory, prefix="build-") as temporary:
            staging = Path(temporary)
            command = [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--wheel-dir",
                str(staging),
            ]
            if not build_isolation:
                command.append("--no-build-isolation")
            command.append(f"{self.distribution} @ git+{self.source['git']}@{self.source['rev']}")
            subprocess.run(command, check=True)
            wheels = list(staging.glob("*.whl"))
            if len(wheels) != 1:
                raise ValueError("The external package build must produce exactly one wheel")
            wheel = wheels[0]
            self._validate_wheel(wheel)
            record = {
                "source": self.source,
                "version": self.version,
                "filename": wheel.name,
                "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            }
            wheel.replace(self.directory / wheel.name)
            metadata = staging / "artifact.json"
            metadata.write_text(json.dumps(record, indent=2) + "\n")
            metadata.replace(self.directory / metadata.name)
        return self.validate()


def build_sdk(
    output_directory: Path,
    *,
    build_isolation: bool = True,
    relay_artifact: Path | None = None,
    contracts_artifact: Path | None = None,
) -> None:
    """Build the selected application distributions without stale generated sources.

    Args:
        output_directory: Destination for the built wheels, created if absent.
        build_isolation: Install build dependencies in pip's isolated environment.
            False uses build tools already installed in the invoking environment.
        contracts_artifact: Prepared external contracts directory for builds without Git access.
        relay_artifact: Prepared external relay directory for builds without Git access.
            None prepares or reuses the host cache from the pinned Git revision.

    Raises:
        OSError: Sources cannot be staged or the destination cannot be created.
        subprocess.CalledProcessError: Pip cannot build the staged project.
    """
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    for distribution, directory in (
        ("coyote-contracts", contracts_artifact),
        ("coyote-relay", relay_artifact),
    ):
        artifact = ExternalArtifact(ROOT, distribution, directory)
        wheel = (
            artifact.validate() if directory else artifact.prepare(build_isolation=build_isolation)
        )
        shutil.copyfile(wheel, output_directory / wheel.name)
    for project in (
        ROOT / "core",
        ROOT,
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
                "demo_build.py",
                "LICENSING.md",
                "THIRD_PARTY_NOTICES.md",
                "CHANGELOG.md",
            ):
                if (project / name).is_file():
                    shutil.copyfile(project / name, staging / name)
            sources: tuple[str, ...]
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
    """Build the selected local and external distributions for deployment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--no-build-isolation", action="store_true")
    parser.add_argument("--relay-artifact", type=Path)
    parser.add_argument("--contracts-artifact", type=Path)
    args = parser.parse_args()
    build_sdk(
        args.output_dir,
        build_isolation=not args.no_build_isolation,
        relay_artifact=args.relay_artifact,
        contracts_artifact=args.contracts_artifact,
    )


if __name__ == "__main__":
    main()
