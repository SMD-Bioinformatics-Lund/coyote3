"""Distribution wheels never contain modules left by an older local build."""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


@pytest.mark.parametrize("distribution", ["client", "core", "api", "mongo"])
def test_wheel_excludes_deleted_modules_from_stale_build_output(tmp_path, distribution):
    """Normal pip wheel builds replace deleted modules in both installable distributions."""
    root = Path(__file__).resolve().parents[2]
    source = {
        "client": root / "clients/python",
        "core": root / "core",
        "api": root / "api",
        "mongo": root / "adapters/mongo",
    }[distribution]
    project = tmp_path / "project"
    project.mkdir()
    for name in [
        "pyproject.toml",
        "README.md",
        "LICENSE.txt",
        "NOTICE.txt",
        "MANIFEST.in",
        "client_build.py"
        if distribution == "client"
        else "build_support.py"
        if distribution == "core"
        else "package_build.py",
    ]:
        shutil.copyfile(source / name, project / name)
    if distribution == "core":
        for name in ["LICENSING.md", "THIRD_PARTY_NOTICES.md"]:
            shutil.copyfile(source / name, project / name)
        shutil.copytree(source / "docs", project / "docs")
    directories = ["src"]
    for name in directories:
        shutil.copytree(
            source / name,
            project / name,
            ignore=shutil.ignore_patterns("*.egg-info", "__pycache__"),
        )
    deleted = (
        ["coyote_pyclient/auth.py", "coyote4_client/__init__.py", "coyote3_client/__init__.py"]
        if distribution == "client"
        else [f"{'coyote_api' if distribution == 'api' else 'coyote_mongo'}/removed_module.py"]
        if distribution in {"api", "mongo"}
        else [
            "coyote3/__init__.py",
            "api/app/deps/auth.py",
            "coyote/obsolete_compatibility.py",
            "coyote/templates/reporting/legacy/dna.html",
            "coyote/templates/reporting/assets/modern.css",
        ]
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
        assert "coyote_pyclient/resources.py" in names
        assert "coyote_pyclient/py.typed" in names
    elif distribution == "core":
        assert not any(name.startswith(("api/", "coyote_api/", "coyote_mongo/")) for name in names)
        assert "coyote/application/reporting/smd_input.py" in names
        assert not any(name.startswith("coyote/templates/reporting/") for name in names)
    else:
        assert (
            "coyote_api/app/main.py" if distribution == "api" else "coyote_mongo/selection.py"
        ) in names
