"""Release records distinguish application compatibility from SDK artifact identity."""

import hashlib
import json
import shutil
import subprocess
import tomllib
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.release import build_sdk
from scripts.release.check_release import (
    RELEASE_CHANGE_SCOPES,
    release_identity,
    source_provenance,
    validate_pull_request,
    wheel_record,
)


def test_core_metadata_does_not_install_a_server_or_database():
    """The core wheel owns its version and never pulls in a concrete host."""
    project = tomllib.loads(Path("core/pyproject.toml").read_text())["project"]
    assert project["name"] == "coyote-core"
    assert "api" not in project["optional-dependencies"]
    assert not any(
        dependency.startswith(("coyote-server", "pymongo", "fastapi"))
        for dependency in project["dependencies"]
    )


@pytest.fixture
def release_root(tmp_path):
    """Supply independently numbered application and SDK release inputs."""
    (tmp_path / "frontend").mkdir()
    (tmp_path / "release.toml").write_text(
        'application_version="4.2.0"\nsdk_version="1.3.1"\nserver_version="1.5.0"\n'
        'relay_version="1.1.0"\n'
        'atlas_version="1.1.0"\ndemo_version="1.1.0"\n'
        "http_api_major=1\ncenter_configuration_format=1\n"
    )
    (tmp_path / "core").mkdir()
    (tmp_path / "core/pyproject.toml").write_text('[project]\nversion="1.3.1"\ndependencies=[]\n')
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="coyote-server"\nversion="1.5.0"\n'
        'dependencies=["coyote-core[reporting,alignment]==1.3.1"]\n'
    )
    source = "https://github.com/example/relay.git"
    commit = "a" * 40
    with (tmp_path / "pyproject.toml").open("a") as output:
        output.write(f'\n[tool.uv.sources]\ncoyote-relay = {{git="{source}", rev="{commit}"}}\n')
    (tmp_path / "uv.lock").write_text(
        f'[[package]]\nname="coyote-relay"\nversion="1.1.0"\n'
        f'source={{git="{source}?rev={commit}#{commit}"}}\n'
    )
    for service in ("atlas", "demo"):
        directory = tmp_path / "services" / service
        directory.mkdir(parents=True)
        dependencies = '["coyote-core==1.3.1"]'
        (directory / "pyproject.toml").write_text(
            f'[project]\nname="coyote-{service}"\nversion="1.1.0"\ndependencies={dependencies}\n'
            '[project.optional-dependencies]\napi=["coyote-server==1.5.0"]\n'
            + (
                'worker=["coyote-server==1.5.0", "coyote-relay==1.1.0"]\n'
                if service == "demo"
                else ""
            )
        )
    for path in ("package.json", "frontend/package.json"):
        (tmp_path / path).write_text(json.dumps({"version": "4.2.0"}))
    routers = tmp_path / "api/src/coyote_api/interfaces/http/v1"
    routers.mkdir(parents=True)
    (routers / "samples.py").write_text('router = APIRouter(prefix="/api/v1/samples")\n')
    identity = tmp_path / "api/src/coyote_api/config/application_release.toml"
    identity.parent.mkdir(parents=True)
    identity.write_text('application_version="4.2.0"\n')
    configuration = tmp_path / "core/src/coyote/config"
    configuration.mkdir(parents=True)
    (configuration / "selection.py").write_text("CENTER_CONFIGURATION_FORMAT = 1\n")
    return tmp_path


def _commit_release_fixture(root):
    """Record a disposable Git baseline without touching the workspace repository."""
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Synthetic",
            "-c",
            "user.email=synthetic@example.test",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Synthetic baseline",
        ],
        cwd=root,
        check=True,
    )
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


@pytest.fixture
def pull_request_release(release_root):
    """Provide complete release notes and a local target commit for PR comparisons."""
    release = release_identity(release_root)
    for field, (changelogs, _) in RELEASE_CHANGE_SCOPES.items():
        for path in changelogs:
            target = release_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# Changelog\n\n## v{release[field]}\n\n- Initial release.\n")
    base = _commit_release_fixture(release_root)
    return release_root, release, base


@pytest.mark.parametrize("skip", [False, True])
def test_pull_request_requires_changelog_edit_unless_waived(pull_request_release, skip):
    root, release, base = pull_request_release
    if skip:
        validate_pull_request(
            root, release, base_ref=base, target_branch="dev", skip_changelog=True
        )
    else:
        with pytest.raises(ValueError, match="Update CHANGELOG.md"):
            validate_pull_request(root, release, base_ref=base, target_branch="dev")


def test_pull_request_into_dev_allows_unchanged_versions(pull_request_release):
    root, release, base = pull_request_release
    changelog = root / "CHANGELOG.md"
    changelog.write_text(changelog.read_text() + "- Correct synthetic behavior.\n")
    validate_pull_request(root, release, base_ref=base, target_branch="dev")


@pytest.mark.parametrize("field", ["application_version", "sdk_version", "server_version"])
def test_pull_request_cannot_decrease_versions(pull_request_release, field):
    root, release, base = pull_request_release
    release[field] = "0.0.1"
    with pytest.raises(ValueError, match=f"{field} cannot decrease"):
        validate_pull_request(
            root, release, base_ref=base, target_branch="dev", skip_changelog=True
        )


def test_pull_request_release_requires_new_application_version_even_with_waiver(
    pull_request_release,
):
    root, release, base = pull_request_release
    with pytest.raises(ValueError, match="Advance application_version"):
        validate_pull_request(
            root, release, base_ref=base, target_branch="master", skip_changelog=True
        )


def test_pull_request_release_rejects_reused_wheel_version(pull_request_release):
    root, release, base = pull_request_release
    release["application_version"] = "4.2.1"
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## v4.2.1\n\n- Core correction.\n")
    source = root / "core/src/coyote/config/selection.py"
    source.write_text(source.read_text() + "SYNTHETIC_NEW_OPTION = True\n")
    with pytest.raises(ValueError, match="Advance sdk_version"):
        validate_pull_request(root, release, base_ref=base, target_branch="master")


def test_pull_request_version_bump_requires_matching_notes(pull_request_release):
    root, release, base = pull_request_release
    release["server_version"] = "1.5.1"
    with pytest.raises(ValueError, match="api/CHANGELOG.md needs a heading"):
        validate_pull_request(
            root, release, base_ref=base, target_branch="dev", skip_changelog=True
        )


def test_pull_request_first_packaged_release_compares_existing_application_version(
    pull_request_release, tmp_path
):
    source, release, _ = pull_request_release
    root = tmp_path / "previous-layout"
    root.mkdir()
    (root / "package.json").write_text('{"version":"3.4.3"}')
    base = _commit_release_fixture(root)
    for path in source.iterdir():
        if path.name in {".git", root.name}:
            continue
        if path.is_dir():
            shutil.copytree(path, root / path.name)
        else:
            shutil.copy2(path, root / path.name)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    validate_pull_request(root, release, base_ref=base, target_branch="master")


def test_application_and_sdk_versions_can_differ(release_root):
    identity = release_identity(release_root)
    assert identity["application_version"] == "4.2.0"
    assert identity["sdk_source_version"] == "1.3.1"
    assert identity["server_version"] == "1.5.0"
    assert identity["relay_version"] == "1.1.0"


def test_application_rejects_a_stale_server_package_selection(release_root):
    path = release_root / "pyproject.toml"
    path.write_text(path.read_text().replace('version="1.5.0"', 'version="1.4.0"'))
    with pytest.raises(ValueError, match="coyote-server version differs"):
        release_identity(release_root)


def test_application_rejects_a_stale_relay_selection(release_root):
    path = release_root / "uv.lock"
    path.write_text(
        path.read_text().replace(
            'name="coyote-relay"\nversion="1.1.0"', 'name="coyote-relay"\nversion="1.0.0"'
        )
    )
    with pytest.raises(ValueError, match="coyote-relay version differs"):
        release_identity(release_root)


def test_application_rejects_a_stale_packaged_application_label(release_root):
    identity = release_root / "api/src/coyote_api/config/application_release.toml"
    identity.write_text('application_version="4.1.0"\n')
    with pytest.raises(ValueError, match="API application identity differs"):
        release_identity(release_root)


def test_application_cannot_silently_build_with_another_sdk(release_root):
    metadata = release_root / "core/pyproject.toml"
    metadata.write_text(metadata.read_text().replace('version="1.3.1"', 'version="1.4.0"'))
    with pytest.raises(ValueError, match="pin differs"):
        release_identity(release_root)
    assert release_identity(release_root, sdk_only=True)["sdk_source_version"] == "1.4.0"


@pytest.mark.parametrize(
    "declaration,valid",
    [
        ("coyote-core[alignment,reporting]==1.3.1", True),
        ("coyote-core[reporting]==1.3.1", False),
        ("coyote-core[alignment,reporting]==1.3.2", False),
    ],
)
def test_server_requires_the_selected_core_and_runtime_features(release_root, declaration, valid):
    """The application must install its renderer and alignment capabilities."""
    metadata = release_root / "pyproject.toml"
    metadata.write_text(
        metadata.read_text().replace("coyote-core[reporting,alignment]==1.3.1", declaration)
    )
    if valid:
        release_identity(release_root)
    else:
        with pytest.raises(ValueError, match="Server core dependency"):
            release_identity(release_root)


@pytest.mark.parametrize(
    "service,old,new,message",
    [
        ("demo", "coyote-relay==1.1.0", "coyote-relay==0.9.0", "Demo worker"),
    ],
)
def test_optional_service_dependencies_match_release_selection(
    release_root, service, old, new, message
):
    """Independent service extras cannot silently pull incompatible release components."""
    project = release_root / "services" / service / "pyproject.toml"
    project.write_text(project.read_text().replace(old, new))
    with pytest.raises(ValueError, match=message):
        release_identity(release_root)


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
        archive.writestr(
            "coyote_core-1.3.1.dist-info/METADATA", f"Name: coyote-core\nVersion: {version}\n"
        )
        archive.writestr("coyote_api/app/main.py" if api_source else "coyote/__init__.py", "")
    if version != "1.3.1" or api_source:
        with pytest.raises(ValueError):
            wheel_record(wheel, "1.3.1")
    else:
        assert (
            wheel_record(wheel, "1.3.1")["sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
        )


def test_retired_sdk_modules_are_rejected_in_built_artifacts(tmp_path):
    wheel = tmp_path / "stale.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "coyote_core-1.3.1.dist-info/METADATA", "Name: coyote-core\nVersion: 1.3.1\n"
        )
        archive.writestr("coyote/application/sdk/old.py", "")
    with pytest.raises(ValueError, match="retired modules"):
        wheel_record(wheel, "1.3.1")


@pytest.mark.parametrize("missing", [None, "coyote_api", "coyote_mongo"])
def test_server_artifact_must_include_both_components(tmp_path, missing):
    wheel = tmp_path / "server.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "coyote_server-1.0.0.dist-info/METADATA", "Name: coyote-server\nVersion: 1.0.0\n"
        )
        for namespace in ("coyote_api", "coyote_mongo"):
            if namespace != missing:
                archive.writestr(f"{namespace}/__init__.py", "")
    if missing:
        with pytest.raises(ValueError, match=f"missing its {missing}/ namespace"):
            wheel_record(wheel, "1.0.0", "coyote-server")
    else:
        assert wheel_record(wheel, "1.0.0", "coyote-server")["version"] == "1.0.0"


def test_release_build_does_not_copy_old_build_outputs(tmp_path, monkeypatch):
    source = tmp_path / "checkout"
    package = source / "core/src/coyote"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Synthetic library."""\n')
    for name in (
        "pyproject.toml",
        "README.md",
        "LICENSE.txt",
        "COPYRIGHT.txt",
        "NOTICE.txt",
        "LICENSING.md",
        "THIRD_PARTY_NOTICES.md",
        "release.toml",
        "build_support.py",
        "MANIFEST.in",
    ):
        (source / "core" / name).write_text("synthetic")
    (source / "core/docs").mkdir(parents=True)
    (source / "core/tests").mkdir()
    (source / "core/docs/architecture.md").write_text("Synthetic core documentation")
    for name in ("pyproject.toml", "LICENSE.txt", "COPYRIGHT.txt", "NOTICE.txt"):
        (source / name).write_text("synthetic")
    for package in (
        "api",
        "adapters/mongo",
        "services/atlas",
        "services/demo",
    ):
        directory = source / package
        (directory / "src").mkdir(parents=True)
        (directory / "docs").mkdir()
        (directory / "tests").mkdir()
        for name in (
            "pyproject.toml",
            "README.md",
            "CHANGELOG.md",
            "LICENSE.txt",
            "COPYRIGHT.txt",
            "NOTICE.txt",
        ):
            (directory / name).write_text("synthetic")
    stale = source / "build/lib/coyote/application/sdk"
    stale.mkdir(parents=True)
    (stale / "old.py").write_text("retired")
    monkeypatch.setattr(build_sdk, "ROOT", source)
    relay_wheel = tmp_path / "coyote_relay-1.2.0-py3-none-any.whl"
    relay_wheel.write_bytes(b"synthetic cached dependency")
    relay = Mock()
    relay.prepare.return_value = relay_wheel
    monkeypatch.setattr(build_sdk, "ExternalArtifact", Mock(return_value=relay))
    inspected = []

    def inspect_build(command, *, check):
        """Inspect staged inputs before their temporary directory is removed."""
        staging = Path(command[-1])
        assert check
        if (staging / "api").exists():
            assert (staging / "api/src").is_dir()
            assert (staging / "adapters/mongo/src").is_dir()
        else:
            assert (staging / "src").is_dir()
        assert (staging / "COPYRIGHT.txt").is_file()
        assert not (staging / "build").exists()
        assert not (staging / "packages").exists()
        assert not (staging / "clients").exists()
        inspected.append(staging)

    monkeypatch.setattr(build_sdk.subprocess, "run", inspect_build)
    build_sdk.build_sdk(tmp_path / "wheels", build_isolation=False)
    assert len(inspected) == 4
    assert all(not path.exists() for path in inspected)


def test_application_startup_rejects_a_different_installed_sdk(monkeypatch):
    from coyote_api.config import bootstrap

    monkeypatch.setattr(bootstrap, "version", lambda name: "999.0.0")
    with pytest.raises(RuntimeError, match="does not match coyote-server's dependency"):
        bootstrap.configure_center_from_environment()


def test_release_generations_match_the_actual_http_routes():
    from coyote_api.app.main import create_api_app

    release = release_identity(Path(__file__).resolve().parents[2])
    paths = create_api_app().openapi()["paths"]
    majors = {int(path.split("/")[2][1:]) for path in paths if path.startswith("/api/v")}
    assert max(majors) == release["http_api_major"]
