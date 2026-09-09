"""Center storage is opt-in and does not impose host or container input paths."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("development", [False, True])
@pytest.mark.parametrize("storage", [0, 1, 3])
def test_center_input_mounts_are_optional_and_shared(development, storage, tmp_path):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose CLI required; no Docker daemon is used")
    command = [
        "docker",
        "compose",
        "--env-file",
        "deploy/env/example.env",
        "-f",
        "deploy/compose/docker-compose.yml",
    ]
    if development:
        command += ["-f", "deploy/compose/docker-compose.dev.yml"]
    if storage:
        storage_file = ROOT / "deploy/compose/docker-compose.storage.example.yml"
        if storage == 3:
            config = yaml.safe_load(storage_file.read_text())
            mounts = config["x-center-inputs"]
            for index in range(2):
                mounts.append(
                    {
                        "type": "bind",
                        "source": f"/synthetic/source-{index}",
                        "target": f"/inputs/tree-{index}",
                        "read_only": True,
                        "bind": {"create_host_path": False},
                    }
                )
            storage_file = tmp_path / "storage.yml"
            storage_file.write_text(yaml.safe_dump(config))
        command += ["-f", str(storage_file)]
    command += ["config", "--format", "json"]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        env={
            **os.environ,
            "COYOTE3_VERSION": "storage-test",
            "CENTER_INPUT_SOURCE": "/synthetic/center/results",
            "CENTER_INPUT_TARGET": "/chosen/inputs",
            "COYOTE3_DATA_HOST_ROOT": "/synthetic/app-data",
        },
    )
    services = json.loads(result.stdout)["services"]
    for name in ("api", "worker", "beat"):
        mounts = {mount["target"]: mount for mount in services[name]["volumes"]}
        assert not {"/access", "/media", "/fs1"}.intersection(mounts)
        assert "/data" in mounts and "/app/logs" in mounts
        assert ("/chosen/inputs" in mounts) is bool(storage)
        data_source = mounts["/data"]["source"]
        assert not any(target.startswith("/data/") for target in mounts)
        assert not mounts["/data"].get("read_only", False)
        if data_source != "/data":
            assert data_source not in mounts
        if storage:
            mount = mounts["/chosen/inputs"]
            assert mount["source"] == "/synthetic/center/results"
            assert mount["read_only"] is True
            # Compose versions may omit the default false value when rendering.
            assert mount.get("bind", {}).get("create_host_path", False) is False
        if storage == 3:
            for index in range(2):
                mount = mounts[f"/inputs/tree-{index}"]
                assert mount["source"] == f"/synthetic/source-{index}"
                assert mount["read_only"] is True
