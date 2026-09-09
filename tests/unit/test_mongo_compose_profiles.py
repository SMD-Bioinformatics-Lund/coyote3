"""Offline Compose rendering: MongoDB must be opt-in, with independent storage."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def render(*profiles, backup_mount=False, backup_root=None):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose is required for offline profile rendering")
    command = [
        "docker",
        "compose",
        "--env-file",
        "deploy/env/example.env",
        "--env-file",
        "deploy/env/example.mongo-split.env",
        "-f",
        "deploy/compose/docker-compose.yml",
        "-f",
        "deploy/compose/docker-compose.mongo.yml",
    ]
    if backup_mount:
        command.extend(["-f", "deploy/compose/docker-compose.mongo-backup.yml"])
    environment = {
        **os.environ,
        "COYOTE3_VERSION": "4.0.0",
        "MONGO_UID": "12345",
        "MONGO_GID": "23456",
    }
    if backup_root is not None:
        environment["COYOTE3_MONGO_BACKUP_HOST_ROOT"] = backup_root
    for profile in profiles:
        command.extend(["--profile", profile])
    result = subprocess.run(
        command + ["config", "--format", "json"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "profiles,expected",
    [
        ((), set()),
        (("mongo",), {"mongo", "mongo_init"}),
        (("mongo-kb",), {"mongo-kb", "mongo_kb_init"}),
        (("mongo", "mongo-kb"), {"mongo", "mongo_init", "mongo-kb", "mongo_kb_init"}),
    ],
)
def test_mongo_services_are_selected_only_by_profile(profiles, expected):
    services = render(*profiles)["services"]
    assert {name for name in services if name.startswith("mongo")} == expected


def test_split_profile_has_independent_replica_sets_and_one_dbpath_per_instance():
    services = render("mongo", "mongo-kb")["services"]
    assert "coyote3-rs" in services["mongo"]["command"]
    assert "coyote3-kb-rs" in services["mongo-kb"]["command"]
    sources = []
    for name in ("mongo", "mongo-kb"):
        service = services[name]
        assert service["environment"]["MONGO_UID"] == "12345"
        assert int(service["mem_limit"]) == 8 * 1024**3
        assert float(service["cpus"]) == 4.0
        assert service["environment"]["MONGO_GID"] == "23456"
        assert service["environment"]["HOME"] == "/tmp"
        assert service["command"][-1] == "/run/coyote3-mongo/keyfile"
        assert service["tmpfs"] == ["/run/coyote3-mongo"]
        assert service["healthcheck"]["test"][1].startswith('gosu "$$MONGO_UID:$$MONGO_GID"')
        assert "security_opt" not in service
        paths = [v for v in services[name]["volumes"] if v["target"] == "/data/db"]
        assert len(paths) == 1
        sources.append(paths[0]["source"])
    assert sources[0] != sources[1]
    for name in ("mongo_init", "mongo_kb_init"):
        assert services[name]["user"] == "12345:23456"
    for name in ("api", "worker", "beat"):
        env = services[name]["environment"]
        assert "mongo-app:27017" in env["COYOTE3_MONGO_URI"]
        assert "mongo-kb:27017" in env["KNOWLEDGEBASE_MONGO_URI"]


@pytest.mark.parametrize("backup_root", ["", "/synthetic/backups"])
def test_backup_mount_is_absent_without_overlay(backup_root):
    services = render("mongo", "mongo-kb", backup_root=backup_root)["services"]
    for name in ("mongo", "mongo-kb"):
        assert all(volume["target"] != "/backup" for volume in services[name]["volumes"])


def test_backup_overlay_preserves_other_mounts_and_knowledgebase_service():
    baseline = render("mongo", "mongo-kb")["services"]
    services = render("mongo", "mongo-kb", backup_mount=True, backup_root="/synthetic/backups")[
        "services"
    ]
    mounts = services["mongo"]["volumes"]
    assert [v for v in mounts if v["target"] != "/backup"] == baseline["mongo"]["volumes"]
    backup = [v for v in mounts if v["target"] == "/backup"]
    assert len(backup) == 1
    assert backup[0]["source"] == "/synthetic/backups"
    # Compose may omit false-valued fields from its normalized JSON output.
    assert backup[0].get("bind", {}).get("create_host_path", False) is False
    assert services["mongo-kb"] == baseline["mongo-kb"]


def test_backup_overlay_requires_explicit_directory():
    with pytest.raises(subprocess.CalledProcessError) as error:
        render("mongo", backup_mount=True, backup_root="")
    assert "COYOTE3_MONGO_BACKUP_HOST_ROOT" in error.value.stderr
