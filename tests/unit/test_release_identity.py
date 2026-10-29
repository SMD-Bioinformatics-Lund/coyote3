"""Release records distinguish application compatibility from SDK artifact identity."""

import hashlib
import json
import tomllib
import zipfile
from pathlib import Path

import pytest

from scripts.release import build_sdk
from scripts.release.check_release import release_identity, source_provenance, wheel_record


def test_aggregate_extra_selects_the_sdk_version_instead_of_application_version():
    """Installing the all extra must not request a different Coyote3 distribution."""
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]
    assert project["optional-dependencies"]["all"] == [
        f"Coyote3[api,dev,test,docs,load]=={project['version']}"
    ]


@pytest.fixture
def release_root(tmp_path):
    """Supply independently numbered application and SDK release inputs."""
    (tmp_path / "frontend").mkdir()
    (tmp_path / "release.toml").write_text(
        'application_version="4.2.0"\nsdk_version="1.3.1"\n'
        "http_api_major=1\ncenter_configuration_format=1\n"
    )
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="1.3.1"\n')
    for path in ("package.json", "frontend/package.json"):
        (tmp_path / path).write_text(json.dumps({"version": "4.2.0"}))
    routers = tmp_path / "api/interfaces/http/v1"
    routers.mkdir(parents=True)
    (routers / "samples.py").write_text('router = APIRouter(prefix="/api/v1/samples")\n')
    configuration = tmp_path / "src/coyote3/config"
    configuration.mkdir(parents=True)
    (configuration / "selection.py").write_text("CENTER_CONFIGURATION_FORMAT = 1\n")
    return tmp_path


def test_application_and_sdk_versions_can_differ(release_root):
    identity = release_identity(release_root)
    assert identity["application_version"] == "4.2.0"
    assert identity["sdk_source_version"] == "1.3.1"


def test_application_cannot_silently_build_with_another_sdk(release_root):
    (release_root / "pyproject.toml").write_text('[project]\nversion="1.4.0"\n')
    with pytest.raises(ValueError, match="pin differs"):
        release_identity(release_root)
    assert release_identity(release_root, sdk_only=True)["sdk_source_version"] == "1.4.0"


def test_application_rejects_stale_frontend_identity(release_root):
    (release_root / "frontend/package.json").write_text('{"version":"4.1.0"}')
    with pytest.raises(ValueError, match="frontend/package.json"):
        release_identity(release_root)


@pytest.mark.parametrize("key", ["http_api_major", "center_configuration_format"])
def test_release_rejects_generations_that_do_not_match_actual_contracts(release_root, key):
    path = release_root / "release.toml"
    path.write_text(path.read_text().replace(f"{key}=1", f"{key}=2"))
    with pytest.raises(ValueError, match=key):
        release_identity(release_root)


def test_production_release_rejects_a_dirty_checkout(release_root, monkeypatch):
    def git_output(command, **kwargs):
        """Supply deterministic source identity and modified-file status."""
        return "a" * 40 if "rev-parse" in command else " M synthetic.py\n"

    monkeypatch.setattr("scripts.release.check_release.subprocess.check_output", git_output)
    with pytest.raises(ValueError, match="clean source checkout"):
        source_provenance(release_root, production=True)
    assert source_provenance(release_root, production=False)["source_dirty"]


@pytest.mark.parametrize(
    "version,api_source", [("1.3.1", False), ("1.4.0", False), ("1.3.1", True)]
)
def test_wheel_record_verifies_the_actual_artifact(tmp_path, version, api_source):
    wheel = tmp_path / "synthetic.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("coyote3-1.3.1.dist-info/METADATA", f"Name: Coyote3\nVersion: {version}\n")
        archive.writestr("api/app/main.py" if api_source else "coyote3/__init__.py", "")
    if version != "1.3.1":
        with pytest.raises(ValueError):
            wheel_record(wheel, "1.3.1")
    else:
        assert (
            wheel_record(wheel, "1.3.1")["sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
        )


def test_retired_sdk_modules_are_rejected_in_built_artifacts(tmp_path):
    wheel = tmp_path / "stale.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("coyote3-1.3.1.dist-info/METADATA", "Name: Coyote3\nVersion: 1.3.1\n")
        archive.writestr("coyote3/application/sdk/old.py", "")
    with pytest.raises(ValueError, match="retired modules"):
        wheel_record(wheel, "1.3.1")


def test_release_build_does_not_copy_old_build_outputs(tmp_path, monkeypatch):
    source = tmp_path / "checkout"
    package = source / "src/coyote3"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Synthetic library."""\n')
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
        (source / name).write_text("synthetic")
    for name in ("api", "config/examples/center", "demo_data/clinical_workflows"):
        (source / name).mkdir(parents=True, exist_ok=True)
    stale = source / "build/lib/coyote3/application/sdk"
    stale.mkdir(parents=True)
    (stale / "old.py").write_text("retired")
    monkeypatch.setattr(build_sdk, "ROOT", source)
    inspected = []

    def inspect_build(command, *, check):
        """Inspect staged inputs before their temporary directory is removed."""
        staging = Path(command[-1])
        assert check
        assert (staging / "src/coyote3/__init__.py").is_file()
        assert not (staging / "build").exists()
        assert (staging / "api").is_dir()
        assert not (staging / "clients").exists()
        inspected.append(staging)

    monkeypatch.setattr(build_sdk.subprocess, "run", inspect_build)
    build_sdk.build_sdk(tmp_path / "wheels", build_isolation=False)
    assert len(inspected) == 1
    assert not inspected[0].exists()


def test_application_startup_rejects_a_different_installed_sdk(monkeypatch):
    from api.config import bootstrap

    monkeypatch.setattr(bootstrap, "version", lambda name: "999.0.0")
    with pytest.raises(RuntimeError, match="does not match release.toml"):
        bootstrap.configure_center_from_environment()


def test_release_generations_match_the_actual_http_routes():
    from api.app.main import create_api_app

    release = release_identity(Path(__file__).resolve().parents[2])
    paths = create_api_app().openapi()["paths"]
    majors = {int(path.split("/")[2][1:]) for path in paths if path.startswith("/api/v")}
    assert max(majors) == release["http_api_major"]
