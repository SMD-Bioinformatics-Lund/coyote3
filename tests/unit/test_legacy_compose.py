"""Check legacy deployment contracts without starting containers or reading private env files."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / "deploy/legacy"


def _render(command, *files, profiles=(), extra_env=None):
    result = subprocess.run(
        [
            *command,
            "-p",
            "legacy-test",
            "--env-file",
            "deploy/env/example.env",
            *[arg for file in files for arg in ("-f", str(LEGACY / file))],
            *[arg for profile in profiles for arg in ("--profile", profile)],
            "config",
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "COYOTE3_VERSION": "legacy-test",
            "COYOTE3_MONGO_URI": "mongodb://mongo-app:27017/?replicaSet=coyote3-rs",
            "COYOTE3_DATA_HOST_ROOT": "/synthetic/data",
            "COYOTE3_REPORTS_HOST_ROOT": "/synthetic/reports",
            "COYOTE3_MONGO_BACKUP_HOST_ROOT": "/synthetic/backups",
            "CENTER_INPUT_SOURCE": "/synthetic/inputs",
            "CENTER_INPUT_TARGET": "/inputs",
            "COYOTE3_DOCKER_HOST_IP": "192.0.2.10",
            **(extra_env or {}),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    document = yaml.safe_load(result.stdout)
    # V1 renders short mount syntax; V2 emits structured volume entries.
    for service in document["services"].values():
        mounts = []
        for mount in service.get("volumes", []):
            if isinstance(mount, str):
                source, target, *options = mount.split(":")
                mount = {"source": source, "target": target, "read_only": "ro" in options}
            mounts.append(mount)
        if mounts:
            service["volumes"] = mounts
    return document


@pytest.fixture(params=["modern", "legacy"])
def compose(request):
    if request.param == "modern":
        command = ["docker", "compose"]
    else:
        command = [os.environ.get("COYOTE3_LEGACY_COMPOSE_BIN", "docker-compose")]
    if not shutil.which(command[0]):
        pytest.skip(f"Compose executable unavailable: {command[0]}")
    result = subprocess.run([*command, "version"], capture_output=True, text=True)
    if result.returncode:
        pytest.skip("Compose executable is not functional")
    if request.param == "legacy":
        assert "1.29.2" in result.stdout, "Use Compose 1.29.2 for the legacy compatibility check"
    return command


def test_application_and_optional_storage_render(compose):
    services = _render(
        compose,
        "docker-compose.yml",
        "docker-compose.host.yml",
        "docker-compose.storage.example.yml",
    )["services"]
    assert not any(name.startswith("mongo") for name in services)
    for name in ("api", "worker", "beat"):
        service = services[name]
        assert "192.0.2.10" in str(service["extra_hosts"])
        mounts = {v["target"]: v for v in service["volumes"]}
        assert mounts["/data/coyote3/reports"]["source"] == "/synthetic/reports"
        assert mounts["/inputs"]["read_only"] is True
        assert service["environment"]["COYOTE3_MONGO_URI"].startswith("mongodb://mongo-app:")
    proxy_script = services["proxy"]["volumes"][0]["source"]
    assert Path(proxy_script).is_file()


@pytest.mark.parametrize("backup", [False, True])
def test_mongo_auth_replica_sets_and_optional_backup(compose, backup):
    files = ["docker-compose.mongo.yml"]
    if backup:
        files.append("docker-compose.mongo-backup.yml")
    services = _render(compose, *files, profiles=("mongo", "mongo-kb"))["services"]
    assert all(service["image"] == "mongo:7.0.41" for service in services.values())
    for name in ("mongo", "mongo-kb"):
        service = services[name]
        assert "--keyFile" in service["command"]
        assert "--replSet" in service["command"]
        assert "extra_hosts" not in service
        mounts = {v["target"]: v for v in service["volumes"]}
        assert "/data/db" in mounts
        assert mounts["/etc/mongo-keyfile/keyfile"]["read_only"] is True
        assert ("/backup" in mounts) is (backup and name == "mongo")
        assert Path(mounts["/docker-entrypoint-initdb.d/01-create-app-user.js"]["source"]).is_file()
    for name in ("mongo_init", "mongo_kb_init"):
        assert Path(services[name]["volumes"][0]["source"]).is_file()


def test_legacy_requires_explicit_report_root(compose):
    with pytest.raises(subprocess.CalledProcessError):
        _render(compose, "docker-compose.yml", extra_env={"COYOTE3_REPORTS_HOST_ROOT": ""})


def test_legacy_application_tracks_modern_service_contract():
    modern = yaml.safe_load((ROOT / "deploy/compose/docker-compose.yml").read_text())
    legacy = yaml.safe_load((LEGACY / "docker-compose.yml").read_text())
    modern.pop("name")
    for service in modern["services"].values():
        service.pop("extra_hosts", None)
    modern_text = yaml.safe_dump(modern)
    modern_text = (
        modern_text.replace(
            "${COYOTE3_MONGO_URI:-${MONGO_URI:-}}",
            "${COYOTE3_MONGO_URI:?COYOTE3_MONGO_URI is required}",
        )
        .replace(
            "${COYOTE3_REPORTS_HOST_ROOT:-${COYOTE3_DATA_HOST_ROOT}/coyote3/reports}",
            "${COYOTE3_REPORTS_HOST_ROOT:?Set an explicit report host directory for legacy Compose}",
        )
        .replace("./nginx/", "../compose/nginx/")
    )
    assert yaml.safe_load(modern_text) == legacy


def test_no_modern_only_syntax_or_security_bypasses():
    for file in LEGACY.glob("*.yml"):
        document = yaml.safe_load(file.read_text())
        assert "name" not in document
        assert "create_host_path" not in yaml.safe_dump(document)
        assert "host-gateway" not in yaml.safe_dump(document)
        for service in document.get("services", {}).values():
            assert not service.get("privileged")
            assert "security_opt" not in service


def test_legacy_mongo_tracks_modern_service_contract():
    modern = yaml.safe_load((ROOT / "deploy/compose/docker-compose.mongo.yml").read_text())
    legacy = yaml.safe_load((LEGACY / "docker-compose.mongo.yml").read_text())
    for service in modern["services"].values():
        service.pop("extra_hosts", None)
        service["image"] = "mongo:7.0.41"
    assert (
        yaml.safe_load(yaml.safe_dump(modern).replace("./mongo-init/", "../compose/mongo-init/"))
        == legacy
    )
