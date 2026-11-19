"""Relay artifacts retain their resources and build without an application checkout."""

import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def stage_project(tmp_path):
    """Stage maintained package inputs without build output or sibling packages."""
    project = tmp_path / "project"
    project.mkdir()
    for name in (
        "pyproject.toml",
        "README.md",
        "LICENSE.txt",
        "COPYRIGHT.txt",
        "NOTICE.txt",
        "CHANGELOG.md",
        "MANIFEST.in",
        "relay_build.py",
    ):
        shutil.copyfile(ROOT / name, project / name)
    for name in ("src", "docs", "tests"):
        shutil.copytree(
            ROOT / name,
            project / name,
            ignore=shutil.ignore_patterns("*.egg-info", "__pycache__", "*.pyc"),
        )
    return project


def build_wheel(project, output):
    """Build with installed tools without resolving or downloading dependencies."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-index",
            "--no-build-isolation",
            "--no-deps",
            "--wheel-dir",
            str(output),
            str(project),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with zipfile.ZipFile(next(output.glob("*.whl"))) as wheel:
        return set(wheel.namelist())


def test_relay_source_distribution_builds_without_repository_siblings(tmp_path):
    """The Relay source archive can build its wheel with no application checkout."""
    project = stage_project(tmp_path)
    output = tmp_path / "sdist"
    output.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"from setuptools.build_meta import build_sdist; build_sdist({str(output)!r})",
        ],
        cwd=project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    archive_path = next(output.glob("*.tar.gz"))
    with tarfile.open(archive_path) as archive:
        members = {str(Path(name).relative_to(Path(name).parts[0])) for name in archive.getnames()}
    assert {
        "pyproject.toml",
        "README.md",
        "LICENSE.txt",
        "COPYRIGHT.txt",
        "NOTICE.txt",
        "docs/README.md",
        "docs/configuration.md",
        "src/coyote_relay/worker.py",
        "src/coyote_relay/assets/coyote-relay-logo.svg",
    } <= members
    assert any(name.startswith("tests/") for name in members)
    assert not any(name.startswith(("api/", "adapters/", "core/", "clients/")) for name in members)
    names = build_wheel(archive_path, tmp_path / "rebuilt-wheels")
    assert {
        "coyote_relay/submit.py",
        "coyote_relay/worker.py",
        "coyote_relay/py.typed",
        "coyote_relay/assets/coyote-relay-logo.svg",
    } <= names
    assert not any(
        name.startswith(("coyote/", "coyote_api/", "coyote_mongo/", "coyote_pyclient/"))
        for name in names
    )
