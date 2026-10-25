"""Container installation rejects wheel drift and invalid production provenance."""

import hashlib
import json
import zipfile

import pytest

from scripts.release.verify_sdk_artifact import verify_compose_artifacts, verify_sdk_artifact


@pytest.fixture
def artifact(tmp_path):
    """Create a synthetic wheel and a matching retained production record."""
    release = tmp_path / "release.toml"
    release.write_text(
        'application_version="4.0.0"\nsdk_version="1.0.0"\nhttp_api_major=1\ncenter_configuration_format=1\n'
    )
    wheel = tmp_path / "coyote3-1.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("coyote3-1.0.0.dist-info/METADATA", "Name: Coyote3\nVersion: 1.0.0\n")
    record = {
        "application_version": "4.0.0",
        "sdk_version": "1.0.0",
        "http_api_major": 1,
        "center_configuration_format": 1,
        "source_commit": "a" * 40,
        "source_dirty": False,
        "release_mode": "production",
        "sdk_artifact": {
            "filename": wheel.name,
            "version": "1.0.0",
            "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        },
    }
    (tmp_path / "release-record.json").write_text(json.dumps(record))
    return tmp_path, release, wheel, record


def test_image_accepts_the_exact_tested_artifact(artifact):
    directory, release, _, record = artifact
    assert (
        verify_sdk_artifact(directory, release, production=True, source_commit="a" * 40) == record
    )


def test_image_rejects_modified_wheel(artifact):
    directory, release, wheel, _ = artifact
    wheel.write_bytes(wheel.read_bytes() + b"modified")
    with pytest.raises(ValueError, match="checksum"):
        verify_sdk_artifact(directory, release, production=True, source_commit="a" * 40)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_dirty", True),
        ("release_mode", "development"),
        ("source_commit", "b" * 40),
        ("sdk_version", "2.0.0"),
        ("http_api_major", 2),
    ],
)
def test_image_rejects_invalid_production_record(artifact, field, value):
    directory, release, _, record = artifact
    record[field] = value
    (directory / "release-record.json").write_text(json.dumps(record))
    with pytest.raises(ValueError):
        verify_sdk_artifact(directory, release, production=True, source_commit="a" * 40)


def test_development_artifact_requires_an_explicit_development_build(artifact):
    directory, release, _, record = artifact
    record.update(source_dirty=True, release_mode="development")
    (directory / "release-record.json").write_text(json.dumps(record))
    assert verify_sdk_artifact(directory, release, production=False)["source_dirty"]
    with pytest.raises(ValueError, match="production release record"):
        verify_sdk_artifact(directory, release, production=True, source_commit="a" * 40)


@pytest.mark.parametrize("failure", [None, "missing", "checksum", "commit", "development"])
def test_compose_preflight_checks_resolved_context_and_provenance(artifact, failure):
    """Installation checks the same artifact identity and provenance as the image build."""
    directory, release, wheel, record = artifact
    if failure == "missing":
        (directory / "release-record.json").unlink()
    elif failure == "checksum":
        wheel.write_bytes(wheel.read_bytes() + b"changed")
    elif failure in {"commit", "development"}:
        if failure == "commit":
            record["source_commit"] = "b" * 40
        else:
            record.update(release_mode="development", source_dirty=True)
        (directory / "release-record.json").write_text(json.dumps(record))
    config = directory / "compose.json"
    config.write_text(
        json.dumps(
            {
                "services": {
                    "api": {
                        "build": {
                            "additional_contexts": {"sdk_artifact": str(directory)},
                            "args": {"GIT_COMMIT": "a" * 40},
                        }
                    }
                }
            }
        )
    )
    if failure:
        with pytest.raises(ValueError, match="COYOTE3_SDK_ARTIFACT_DIR"):
            verify_compose_artifacts(config, release)
    else:
        verify_compose_artifacts(config, release)


def test_editable_development_build_needs_no_wheel_context(tmp_path):
    """Development overlays without a named SDK context retain their source build path."""
    config = tmp_path / "compose.json"
    config.write_text(json.dumps({"services": {"api": {"build": {"context": "."}}}}))
    verify_compose_artifacts(config, tmp_path / "unused-release.toml")
