"""Demo deployment preparation never inherits a clinical environment or starts services."""

import json
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
import yaml

from deploy.installer import demo, demo_bootstrap


def test_prepare_ignores_ambient_connections_and_generates_distinct_credentials(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("COYOTE4_MONGO_URI", "mongodb://prod.example.invalid")
    monkeypatch.setenv("COYOTE4_DB", "coyote4_prod")
    monkeypatch.setenv("SECRET_KEY", "ambient-secret")
    path = demo.prepare(tmp_path / "demo", mode="docker", port=8089)
    settings = json.loads(path.read_text())
    environment = settings["environment"]
    assert environment["COYOTE4_DB"] == "coyote4_demo"
    assert environment["SECRET_KEY"] != "ambient-secret"
    assert "prod.example.invalid" not in path.read_text()
    secrets = [
        environment[key] for key in ("SECRET_KEY", "INTERNAL_API_TOKEN", "PASSWORD_TOKEN_SALT")
    ]
    assert len(set(secrets)) == 3
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    with pytest.raises(ValueError, match="new or empty"):
        demo.prepare(path.parent, mode="docker", port=8089)


def test_native_settings_require_explicit_local_restricted_endpoints(tmp_path):
    with pytest.raises(ValueError, match="explicit"):
        demo.prepare(tmp_path / "missing", mode="native", port=8089)
    path = demo.prepare(
        tmp_path / "native",
        mode="native",
        port=8089,
        mongo="mongodb://coyote_demo:synthetic@127.0.0.1:27028/?authSource=admin&replicaSet=demo-rs&directConnection=true",
        redis="redis://default:synthetic@127.0.0.1:16379",
    )
    settings = demo.load_settings(path.parent)
    assert settings["environment"]["COYOTE4_DATA_ROOT"] == str(path.parent / "data")
    (path.parent / "runtime/.env").write_text("COYOTE4_DB=coyote4_prod")
    with pytest.raises(ValueError, match="isolated runtime"):
        demo.load_settings(path.parent)


@pytest.mark.parametrize(
    "service,mode", [("worker", "ingest"), ("maintenance-worker", "maintenance"), ("beat", "beat")]
)
def test_native_worker_uses_current_interpreter_and_guarded_wrapper(
    tmp_path, monkeypatch, service, mode
):
    path = demo.prepare(
        tmp_path / "native",
        mode="native",
        port=8089,
        mongo="mongodb://coyote_demo:synthetic@127.0.0.1:27028/?authSource=admin&replicaSet=demo-rs&directConnection=true",
        redis="redis://default:synthetic@127.0.0.1:16379",
    )
    calls = []
    monkeypatch.setattr(
        demo.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)) or SimpleNamespace(returncode=0),
    )
    assert demo.main(["--directory", str(path.parent), "run", service]) == 0
    command, options = calls[0]
    assert command[:3] == [demo.sys.executable, "-m", "coyote_demo.runtime"]
    assert command[3] == mode
    assert options["cwd"] == path.parent / "runtime"


def test_demo_bootstrap_requires_enabled_isolation_before_any_host_bootstrap(monkeypatch):
    monkeypatch.delenv("COYOTE_DEMO_ENABLED", raising=False)
    monkeypatch.setattr(
        demo_bootstrap.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("Unexpected bootstrap"),
    )
    with pytest.raises(ValueError, match="COYOTE_DEMO_ENABLED"):
        demo_bootstrap.main()


def test_saved_project_cannot_select_an_existing_normal_deployment(tmp_path):
    path = demo.prepare(tmp_path / "demo", mode="docker", port=8089)
    record = json.loads(path.read_text())
    record["compose"]["COYOTE_DEMO_PROJECT"] = "coyote4_prod"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="isolated name"):
        demo.load_settings(path.parent)


def test_compose_invocation_cannot_use_ambient_env_context_or_overlays(tmp_path, monkeypatch):
    path = demo.prepare(tmp_path / "demo", mode="docker", port=8089)
    monkeypatch.setenv("DOCKER_HOST", "ssh://prod.example.invalid")
    monkeypatch.setenv("COMPOSE_FILE", "production.yml")
    monkeypatch.setenv("COYOTE4_MONGO_URI", "mongodb://prod.example.invalid")
    calls = []
    monkeypatch.setattr(
        demo.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)) or SimpleNamespace(returncode=0),
    )
    assert demo.main(["--directory", str(path.parent), "compose", "config"]) == 0
    command, options = calls[0]
    assert command[1:3] == ["--host", "unix:///var/run/docker.sock"]
    assert command[-2:] == ["config", "--quiet"]
    assert command[command.index("--env-file") + 1] == "/dev/null"
    assert "DOCKER_HOST" not in options["env"]
    assert "COMPOSE_FILE" not in options["env"]
    assert "prod.example.invalid" not in options["env"]["COYOTE4_MONGO_URI"]


def test_compose_has_only_project_scoped_resources_and_loopback_exposure():
    compose = yaml.safe_load((demo.ROOT / "deploy/demo/compose.yml").read_text())
    assert compose["networks"] == {"demo": {"internal": True}}
    assert all(value is None for value in compose["volumes"].values())
    for name, service in compose["services"].items():
        assert service["networks"] == ["demo"]
        assert "env_file" not in service
        assert "network_mode" not in service
        assert "extra_hosts" not in service
        assert "container_name" not in service
        for volume in service.get("volumes", []):
            assert volume.split(":")[0] in compose["volumes"]
        if name != "frontend":
            assert "ports" not in service
    assert compose["services"]["frontend"]["ports"] == ["127.0.0.1:${COYOTE_DEMO_PORT:?}:3000"]
    environment = compose["services"]["api"]["environment"]
    for key in (
        "COYOTE4_MONGO_URI",
        "IDENTITY_MONGO_URI",
        "KNOWLEDGEBASE_MONGO_URI",
        "BAM_MONGO_URI",
    ):
        uri = environment[key].replace("${COYOTE_DEMO_MONGO_PASSWORD:?}", "synthetic")
        assert urlsplit(uri).hostname == "demo-mongo"
    assert environment["AUTHENTICATION_PROVIDERS"] == "local"
    assert environment["COYOTE4_RUNTIME_MODE"] == "production"
    assert environment["ENV_NAME"] == "testing"
    assert environment["COYOTE4_INGEST_WATCH_ENABLED"] == "0"
    assert compose["services"]["api"]["build"]["target"] == "demo_source"
    for name, mode in (
        ("worker", "ingest"),
        ("maintenance-worker", "maintenance"),
        ("beat", "beat"),
    ):
        assert compose["services"][name]["command"][:4] == [
            "python3",
            "-m",
            "coyote_demo.runtime",
            mode,
        ]
