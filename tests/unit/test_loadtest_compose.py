"""Keep the load generator optional and separate from application secrets and storage."""

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "deploy/compose/docker-compose.loadtest.yml"


def test_load_generator_is_opt_in_and_least_privilege():
    """The optional profile exposes only loopback UI and its own writable results."""
    config = yaml.safe_load(COMPOSE.read_text())
    assert set(config["services"]) == {"loadtest"}
    service = config["services"]["loadtest"]
    assert service["profiles"] == ["loadtest"]
    assert "depends_on" not in service
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert service["restart"] == "no"
    assert all(port.startswith("127.0.0.1:") for port in service["ports"])
    mounts = {mount["target"]: mount for mount in service["volumes"]}
    assert set(mounts) == {"/mnt/locust", "/load/private", "/load/results"}
    assert mounts["/mnt/locust"]["read_only"] is True
    assert mounts["/load/private"]["read_only"] is True
    assert all(mount["bind"]["create_host_path"] is False for mount in mounts.values())
    assert not any("MONGO" in key or "TOKEN" in key for key in service["environment"])
    assert config["networks"]["load_target"]["external"] is True


def test_load_dependency_is_separate_and_matches_container():
    """The generator pin agrees across packaging, standalone export and image."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    requirements = [
        line
        for line in (ROOT / "requirements-load.txt").read_text().splitlines()
        if line and not line.startswith("#")
    ]
    assert requirements == project["optional-dependencies"]["load"]
    assert len(requirements) == 1
    name, version = requirements[0].split("==")
    assert name == "locust"
    assert yaml.safe_load(COMPOSE.read_text())["services"]["loadtest"]["image"] == (
        f"locustio/locust:{version}"
    )
    assert not any(dep.startswith("locust") for dep in project["dependencies"])


def test_loadtest_compose_resolves_without_application_environment():
    """Compose parsing requires neither a daemon nor clinical deployment variables."""
    if not shutil.which("docker"):
        pytest.skip("Docker Compose CLI is unavailable")
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            "deploy/env/example.loadtest.env",
            "-f",
            str(COMPOSE),
            "--profile",
            "loadtest",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"], "HOME": os.environ["HOME"]},
        capture_output=True,
        text=True,
        check=True,
    )
    services = json.loads(result.stdout)["services"]
    assert set(services) == {"loadtest"}
    assert services["loadtest"]["ports"][0]["host_ip"] == "127.0.0.1"
