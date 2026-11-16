"""Deployment distributions rebuild cleanly from source and source archives."""

import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def stage_project(tmp_path, distribution):
    """Copy maintained build inputs into a checkout-independent source directory."""
    source = {
        "client": ROOT / "clients/python",
        "core": ROOT / "core",
        "server": ROOT,
        "ingest": ROOT / "services/ingest",
    }[distribution]
    project = tmp_path / "project"
    project.mkdir()
    for name in (
        "pyproject.toml",
        "README.md",
        "LICENSE.txt",
        "COPYRIGHT.txt",
        "NOTICE.txt",
        "LICENSING.md",
        "THIRD_PARTY_NOTICES.md",
        "CHANGELOG.md",
        "MANIFEST.in",
        "client_build.py",
        "ingest_build.py",
        "build_support.py",
        "package_build.py",
    ):
        if (source / name).is_file():
            shutil.copyfile(source / name, project / name)
    components = ("api", "adapters/mongo") if distribution == "server" else (".",)
    for component in components:
        target = project / component
        target.mkdir(parents=True, exist_ok=True)
        if component != ".":
            for name in (
                "README.md",
                "CHANGELOG.md",
                "pyproject.toml",
                "LICENSE.txt",
                "COPYRIGHT.txt",
                "NOTICE.txt",
            ):
                shutil.copyfile(source / component / name, target / name)
        for name in ("src", "docs", "tests"):
            shutil.copytree(
                source / component / name,
                target / name,
                ignore=shutil.ignore_patterns("*.egg-info", "__pycache__", "*.pyc"),
            )
    return project


def build_wheel(project, output):
    """Build an actual wheel using installed tools without fetching dependencies."""
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


@pytest.mark.parametrize("distribution", ["client", "core", "server", "ingest"])
def test_wheel_excludes_deleted_modules_from_stale_build_output(tmp_path, distribution):
    """All distributions discard files removed since a previous wheel build."""
    project = stage_project(tmp_path, distribution)
    deleted = {
        "client": [
            "coyote_pyclient/auth.py",
            "coyote4_client/__init__.py",
            "coyote3_client/__init__.py",
        ],
        "core": [
            "coyote3/__init__.py",
            "api/app/deps/auth.py",
            "coyote/obsolete_compatibility.py",
            "coyote/templates/reporting/legacy/dna.html",
            "coyote/templates/reporting/assets/modern.css",
        ],
        "server": ["coyote_api/removed_module.py", "coyote_mongo/removed_module.py"],
        "ingest": ["coyote_ingest/removed_module.py", "coyote_api/tasks/ingest.py"],
    }[distribution]
    for name in deleted:
        stale = project / "build/lib" / name
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text('"""Removed implementation."""\n')
    names = build_wheel(project, tmp_path / "wheels")
    assert not set(deleted).intersection(names)
    if distribution == "client":
        assert "coyote_pyclient/resources.py" in names
        assert "coyote_pyclient/py.typed" in names
    elif distribution == "core":
        assert not any(name.startswith(("api/", "coyote_api/", "coyote_mongo/")) for name in names)
        assert "coyote/application/reporting/smd_input.py" in names
        assert not any(name.startswith("coyote/templates/reporting/") for name in names)
    elif distribution == "server":
        assert "coyote_api/app/main.py" in names
        assert "coyote_mongo/selection.py" in names
        assert not any(name.startswith(("coyote/", "coyote_pyclient/")) for name in names)
    else:
        assert "coyote_ingest/worker.py" in names
        assert "coyote_ingest/py.typed" in names
        assert not any(
            name.startswith(("coyote/", "coyote_pyclient/", "coyote_api/", "coyote_mongo/"))
            for name in names
        )


def test_server_source_distribution_rebuilds_both_components_without_checkout(tmp_path):
    """An extracted server sdist retains component source, docs, tests and runtime resources."""
    project = stage_project(tmp_path, "server")
    for component, package in (("api", "coyote_api"), ("adapters/mongo", "coyote_mongo")):
        retired_metadata = project / component / "src" / f"{package}.egg-info"
        retired_metadata.mkdir()
        (retired_metadata / "PKG-INFO").write_text("Retired independent distribution metadata")
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
        "package_build.py",
        "api/README.md",
        "api/pyproject.toml",
        "api/LICENSE.txt",
        "adapters/mongo/pyproject.toml",
        "adapters/mongo/LICENSE.txt",
        "api/src/coyote_api/app/main.py",
        "adapters/mongo/src/coyote_mongo/selection.py",
        "api/docs/README.md",
        "adapters/mongo/docs/README.md",
    } <= members
    assert any(name.startswith("api/tests/") for name in members)
    assert any(name.startswith("adapters/mongo/tests/") for name in members)
    assert not any(name.startswith(("core/", "clients/", ".design/")) for name in members)
    assert not any(
        "coyote_api.egg-info" in name or "coyote_mongo.egg-info" in name for name in members
    )
    names = build_wheel(archive_path, tmp_path / "rebuilt-wheels")
    assert {
        "coyote_api/app/main.py",
        "coyote_api/config/application_release.toml",
        "coyote_api/app/templates/api_reference.html",
        "coyote_mongo/selection.py",
        "coyote_mongo/config/collections.toml",
    } <= names
