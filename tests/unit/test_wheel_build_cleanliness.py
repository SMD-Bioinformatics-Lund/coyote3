"""Distribution wheels never contain modules left by an older local build."""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


@pytest.mark.parametrize("distribution", ["client", "core"])
def test_wheel_excludes_deleted_modules_from_stale_build_output(tmp_path, distribution):
    """Normal pip wheel builds replace deleted modules in both installable distributions."""
    root = Path(__file__).resolve().parents[2]
    source = root / "clients/python" if distribution == "client" else root
    project = tmp_path / "project"
    project.mkdir()
    for name in [
        "pyproject.toml",
        "README.md",
        "LICENSE.txt",
        "NOTICE.txt",
        "MANIFEST.in",
        "client_build.py" if distribution == "client" else "build_support.py",
    ]:
        shutil.copyfile(source / name, project / name)
    if distribution == "core":
        for name in ["release.toml", "LICENSING.md", "THIRD_PARTY_NOTICES.md"]:
            shutil.copyfile(source / name, project / name)
    directories = (
        ["src"]
        if distribution == "client"
        else ["src/coyote3", "api", "config/examples/center", "demo_data/clinical_workflows"]
    )
    for name in directories:
        shutil.copytree(
            source / name,
            project / name,
            ignore=shutil.ignore_patterns("*.egg-info", "__pycache__"),
        )
    deleted = (
        ["coyote3_client/auth.py"]
        if distribution == "client"
        else ["api/app/deps/auth.py", "coyote3/obsolete_compatibility.py"]
    )
    for name in deleted:
        stale = project / "build/lib" / name
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text('"""Removed implementation."""\n')
    output = tmp_path / "wheels"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-build-isolation",
            "--no-deps",
            "--wheel-dir",
            str(output),
            str(project),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(next(output.glob("*.whl"))) as wheel:
        names = wheel.namelist()
    assert not set(deleted).intersection(names)
    if distribution == "client":
        assert "coyote3_client/resources.py" in names
        assert "coyote3_client/py.typed" in names
    else:
        assert "api/app/main.py" in names
        assert "coyote3/templates/reporting/assets/modern.css" in names
