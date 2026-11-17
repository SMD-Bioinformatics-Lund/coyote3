"""External relay builds bind the selected Git revision to a verified local wheel."""

import json
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from deploy.installer import compose
from scripts.release import build_sdk
from scripts.release.build_sdk import ExternalArtifact


@pytest.fixture
def selection(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.uv.sources]\ncoyote-relay = "
        '{git="https://github.com/example/relay.git", rev="' + "a" * 40 + '"}\n'
    )
    (tmp_path / "release.toml").write_text('relay_version="1.0.0"\n')
    return tmp_path


@pytest.fixture
def builder(monkeypatch):
    """Simulate pip output without network or dependency installation."""

    def build(command, *, check):
        assert check
        assert command[-1].endswith("@" + "a" * 40)
        directory = Path(command[command.index("--wheel-dir") + 1])
        with zipfile.ZipFile(directory / "coyote_relay-1.0.0-py3-none-any.whl", "w") as wheel:
            wheel.writestr(
                "coyote_relay-1.0.0.dist-info/METADATA",
                "Name: coyote-relay\nVersion: 1.0.0\n",
            )

    process = Mock(side_effect=build)
    monkeypatch.setattr(build_sdk.subprocess, "run", process)
    return process


def test_matching_cache_is_reused_without_network(selection, builder):
    artifact = ExternalArtifact(selection, "coyote-relay")
    wheel = artifact.prepare(build_isolation=False)
    assert artifact.prepare() == artifact.validate() == wheel
    builder.assert_called_once()
    assert "--no-build-isolation" in builder.call_args.args[0]


@pytest.mark.parametrize("change", ["version", "source", "filename", "sha256"])
def test_invalid_artifact_record_cannot_be_consumed(selection, builder, change):
    artifact = ExternalArtifact(selection, "coyote-relay")
    artifact.prepare()
    path = artifact.directory / "artifact.json"
    record = json.loads(path.read_text())
    record[change] = "../untrusted.whl" if change == "filename" else "changed"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        artifact.validate()
    builder.assert_called_once()


def test_corrupt_wheel_is_rebuilt_before_reuse(selection, builder):
    artifact = ExternalArtifact(selection, "coyote-relay")
    artifact.prepare().write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        artifact.validate()
    artifact.prepare()
    artifact.validate()
    assert builder.call_count == 2


@pytest.mark.parametrize(
    "old,new",
    [
        ("a" * 40, "dev"),
        ("https://github.com", "https://synthetic-token@github.com"),
        ("https://github.com", "ssh://github.com"),
    ],
)
def test_unpinned_or_credential_bearing_sources_are_rejected(selection, old, new):
    metadata = selection / "pyproject.toml"
    metadata.write_text(metadata.read_text().replace(old, new))
    with pytest.raises(ValueError, match="HTTPS Git URL and full commit"):
        ExternalArtifact(selection, "coyote-relay")


@pytest.mark.parametrize(
    "target,expected",
    [("coyote4_source_api", True), ("coyote4_dev_api", True), ("coyote4_verified_api", False)],
)
def test_only_source_image_builds_prepare_external_dependencies(monkeypatch, target, expected):
    relay = Mock()
    monkeypatch.setattr(compose, "ExternalArtifact", Mock(return_value=relay))
    operation = object.__new__(compose.Compose)
    operation._config = {"services": {"api": {"build": {"target": target}}}}
    operation._executable = ["synthetic-compose"]
    operation.profile = Mock()
    operation.profile.arguments.return_value = []
    operation.runner = Mock()
    operation.run(["build"])
    assert relay.prepare.call_count == (2 if expected else 0)
