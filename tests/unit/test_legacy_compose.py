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
            "MONGO_UID": "12345",
            "MONGO_GID": "23456",
            "COYOTE3_MONGO_URI": "mongodb://mongo-app:27017/?replicaSet=coyote3-rs",
            "COYOTE3_DATA_HOST_ROOT": "/synthetic/data",
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
    for name in ("api", "frontend", "docs"):
        assert services[name]["build"]["network"] == "host"
    for name in ("api", "docs"):
        assert services[name]["build"]["args"]["PYTHON_BASE_IMAGE"] == "python:3.12-slim-bullseye"
    assert all(service.get("network_mode") != "host" for service in services.values())
    for name in ("api", "worker", "beat"):
        service = services[name]
        assert "192.0.2.10" in str(service["extra_hosts"])
        mounts = {v["target"]: v for v in service["volumes"]}
        assert mounts["/data"]["source"] == "/synthetic/data"
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
    assert all(
        str(service["mem_limit"]) in {"8g", str(8 * 1024**3)} for service in services.values()
    )
    assert all(float(service["cpus"]) == 4.0 for service in services.values())
    for name in ("mongo", "mongo-kb"):
        service = services[name]
        assert "--keyFile" in service["command"]
        assert "--replSet" in service["command"]
        assert service["environment"]["MONGO_UID"] == "12345"
        assert service["environment"]["MONGO_GID"] == "23456"
        assert "extra_hosts" not in service
        mounts = {v["target"]: v for v in service["volumes"]}
        assert "/data/db" in mounts
        assert mounts["/etc/mongo-keyfile/keyfile"]["read_only"] is True
        assert service["command"][-1] == "/run/coyote3-mongo/keyfile"
        assert service["tmpfs"] == ["/run/coyote3-mongo"]
        assert service["entrypoint"] == ["/bin/sh", "/opt/coyote3/mongo-entrypoint.sh"]
        assert mounts["/opt/coyote3/mongo-entrypoint.sh"]["read_only"] is True
        assert Path(mounts["/opt/coyote3/mongo-entrypoint.sh"]["source"]).is_file()
        assert ("/backup" in mounts) is (backup and name == "mongo")
        assert Path(mounts["/docker-entrypoint-initdb.d/01-create-app-user.js"]["source"]).is_file()
    for name in ("mongo_init", "mongo_kb_init"):
        assert services[name]["user"] == "12345:23456"
        assert Path(services[name]["volumes"][0]["source"]).is_file()


def test_legacy_requires_explicit_data_root(compose):
    with pytest.raises(subprocess.CalledProcessError):
        _render(compose, "docker-compose.yml", extra_env={"COYOTE3_DATA_HOST_ROOT": ""})


def test_legacy_dev_has_isolated_images_and_live_source(compose):
    services = _render(compose, "docker-compose.dev.yml")["services"]
    frontend = services["frontend"]
    assert frontend["image"] == "node:22-alpine"
    assert "build" not in frontend
    assert "npm run dev" in str(frontend["command"])
    assert frontend["environment"]["COYOTE3_API_INTERNAL_URL"] == "http://api:8001"
    for name in ("api", "worker", "beat"):
        assert services[name]["image"] == "coyote3-api:legacy-test-dev"
        mounts = {mount["target"]: mount for mount in services[name]["volumes"]}
        assert mounts["/app/api"]["source"] == str(ROOT / "api")
        assert "/data" in mounts
        assert not any(target.startswith("/data/") for target in mounts)
    assert "--reload" in services["api"]["command"]
    assert services["api"]["build"]["args"]["PYTHON_BASE_IMAGE"] == "python:3.12-slim-bullseye"
    assert services["docs"]["image"] == "coyote3-docs:legacy-test-dev"


@pytest.mark.parametrize("environment", ["stage", "test"])
def test_legacy_environment_images_and_profiles(compose, environment):
    services = _render(
        compose,
        "docker-compose.yml",
        f"docker-compose.{environment}.yml",
        profiles=("with-ui", "tests") if environment == "test" else (),
    )["services"]
    for name in ("api", "worker", "beat", "frontend", "docs"):
        image_name = "api" if name in {"worker", "beat"} else name
        assert services[name]["image"] == f"coyote3-{image_name}:legacy-test-{environment}"
    if environment == "test":
        assert services["test_runner"]["profiles"] == ["tests"]
        for name in ("api", "worker", "beat", "test_runner"):
            assert services[name]["build"]["network"] == "host"
            assert (
                services[name]["build"]["args"]["PYTHON_BASE_IMAGE"] == "python:3.12-slim-bullseye"
            )


@pytest.mark.parametrize("environment", ["dev", "stage", "test"])
def test_legacy_environment_tracks_modern_contract(compose, environment):
    if len(compose) == 1:
        pytest.skip("Modern overlays require Compose v2")
    profiles = ("with-ui", "tests") if environment == "test" else ()
    modern = _render(
        compose,
        ROOT / "deploy/compose/docker-compose.yml",
        ROOT / f"deploy/compose/docker-compose.{environment}.yml",
        profiles=profiles,
    )["services"]
    files = [f"docker-compose.{environment}.yml"]
    if environment != "dev":
        files.insert(0, "docker-compose.yml")
    legacy = _render(compose, *files, profiles=profiles)["services"]
    assert legacy.keys() == modern.keys()
    for name, service in modern.items():
        for field in ("image", "environment", "command", "profiles", "healthcheck"):
            assert legacy[name].get(field) == service.get(field), (name, field)
        modern_mounts = {
            mount["target"]: (mount["source"], mount.get("read_only", False))
            for mount in service.get("volumes", [])
        }
        legacy_mounts = {
            mount["target"]: (mount["source"], mount.get("read_only", False))
            for mount in legacy[name].get("volumes", [])
        }
        assert legacy_mounts == modern_mounts, name


def test_legacy_application_tracks_modern_service_contract():
    modern = yaml.safe_load((ROOT / "deploy/compose/docker-compose.yml").read_text())
    legacy = yaml.safe_load((LEGACY / "docker-compose.yml").read_text())
    modern.pop("name")
    modern["services"]["redis"]["security_opt"] = ["seccomp=unconfined"]
    modern["services"]["beat"]["ipc"] = "none"
    for name in ("api", "frontend", "docs"):
        modern["services"][name]["build"]["network"] = "host"
    for name in ("api", "docs"):
        modern["services"][name]["build"]["args"]["PYTHON_BASE_IMAGE"] = "python:3.12-slim-bullseye"
    for service in modern["services"].values():
        service.pop("extra_hosts", None)
    modern_text = yaml.safe_dump(modern)
    modern_text = modern_text.replace(
        "${COYOTE3_MONGO_URI:-${MONGO_URI:-}}",
        "${COYOTE3_MONGO_URI:?COYOTE3_MONGO_URI is required}",
    ).replace("./nginx/", "../compose/nginx/")
    assert yaml.safe_load(modern_text) == legacy


def test_no_modern_only_syntax_or_unscoped_security_bypasses():
    for file in LEGACY.glob("*.yml"):
        document = yaml.safe_load(file.read_text())
        assert "name" not in document
        assert "create_host_path" not in yaml.safe_dump(document)
        assert "host-gateway" not in yaml.safe_dump(document)
        for name, service in document.get("services", {}).items():
            assert not service.get("privileged")
            if file.name == "docker-compose.mongo.yml" and name in (
                "mongo",
                "mongo_init",
                "mongo-kb",
                "mongo_kb_init",
            ):
                assert service["security_opt"] == ["seccomp=unconfined"]
            else:
                if (
                    file.name in {"docker-compose.yml", "docker-compose.dev.yml"}
                    and name == "redis"
                ):
                    assert service["security_opt"] == ["seccomp=unconfined"]
                else:
                    assert "security_opt" not in service


def test_legacy_mongo_tracks_modern_service_contract():
    modern = yaml.safe_load((ROOT / "deploy/compose/docker-compose.mongo.yml").read_text())
    legacy = yaml.safe_load((LEGACY / "docker-compose.mongo.yml").read_text())
    for service in modern["services"].values():
        service.pop("extra_hosts", None)
        service["image"] = "mongo:7.0.41"
        service["security_opt"] = ["seccomp=unconfined"]
    assert (
        yaml.safe_load(yaml.safe_dump(modern).replace("./mongo-init/", "../compose/mongo-init/"))
        == legacy
    )
