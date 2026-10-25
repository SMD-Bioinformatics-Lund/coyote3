"""Compose can build a source installation without a retained SDK artifact directory."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("retained_artifact", [False, True])
def test_compose_selects_source_or_verified_artifact_build(retained_artifact, tmp_path):
    """The normal build needs no SDK directory; the release overlay opts into verification."""
    if not shutil.which("docker"):
        pytest.skip("Docker Compose CLI is not installed")
    available = subprocess.run(["docker", "compose", "version"], capture_output=True)
    if available.returncode:
        pytest.skip("Docker Compose CLI is not available")
    command = [
        "docker",
        "compose",
        "--env-file",
        str(ROOT / "deploy/env/example.env"),
        "-f",
        str(ROOT / "deploy/compose/docker-compose.yml"),
    ]
    if retained_artifact:
        command += ["-f", str(ROOT / "deploy/compose/docker-compose.release.yml")]
    command += ["config", "--format", "json"]
    absent_directory = tmp_path / "missing-sdk"
    result = subprocess.run(
        command,
        env={
            **os.environ,
            "COYOTE3_IMAGE_TAG": "installation-test",
            "COYOTE3_SDK_ARTIFACT_DIR": str(absent_directory),
        },
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    build = json.loads(result.stdout)["services"]["api"]["build"]
    if retained_artifact:
        assert build["target"] == "coyote3_api"
        assert build["additional_contexts"]["sdk_artifact"] == str(absent_directory)
    else:
        assert build["target"] == "coyote3_source_api"
        assert "sdk_artifact" not in build.get("additional_contexts", {})
    assert not absent_directory.exists()
