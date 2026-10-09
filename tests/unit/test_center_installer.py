"""Exercise installation orchestration without Docker, network or real databases."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock

import mongomock
import pytest

from scripts.deployment.installation_checks import (
    check_indexes,
    installation_state,
    validate_maintenance_endpoint,
)

ROOT = Path(__file__).resolve().parents[2]


def test_target_detection_preserves_existing_and_rejects_partial_installations():
    client = mongomock.MongoClient()
    assert installation_state(client.application, client.identity) == "fresh"
    client.application.samples.insert_one({"name": "synthetic"})
    with pytest.raises(ValueError, match="Partial"):
        installation_state(client.application, client.identity)
    client.identity.users.insert_many([{"roles": ["superuser"]}, {"roles": ["sys_admin"]}])
    client.identity.roles.insert_one({"role_id": "superuser"})
    client.identity.permissions.insert_one({"permission_id": "synthetic"})
    before = list(client.identity.users.find())
    assert installation_state(client.application, client.identity) == "existing"
    assert list(client.identity.users.find()) == before


def test_maintenance_credentials_cannot_redirect_knowledgebase(monkeypatch):
    for key, value in {
        "COYOTE3_MONGO_URI": "mongodb://reader@synthetic.invalid/?replicaSet=example",
        "COYOTE3_DB": "application",
        "IDENTITY_DB": "identity",
        "KNOWLEDGEBASE_DB": "knowledgebase",
        "BAM_DB": "bam",
        "COYOTE_INSTALL_KB_URI": "mongodb://maintainer@synthetic.invalid/?replicaSet=example",
    }.items():
        monkeypatch.setenv(key, value)
    for key in ("IDENTITY_MONGO_URI", "KNOWLEDGEBASE_MONGO_URI", "BAM_MONGO_URI"):
        monkeypatch.delenv(key, raising=False)
    validate_maintenance_endpoint()
    monkeypatch.setenv("COYOTE_INSTALL_KB_URI", "mongodb://other.invalid/?replicaSet=example")
    with pytest.raises(ValueError, match="runtime hosts"):
        validate_maintenance_endpoint()


@pytest.fixture
def fake_installation(tmp_path):
    """Supply executable doubles; every deployment subprocess stays inside this fixture."""
    deployment = tmp_path / "scripts/deployment"
    deployment.mkdir(parents=True)
    shutil.copy(ROOT / "scripts/deployment/install_center.sh", deployment)
    (tmp_path / "api").mkdir()
    (tmp_path / "api/version.py").write_text('print("synthetic")\n')
    (deployment / "validate_env_secrets.sh").write_text("#!/bin/bash\nexit 0\n")
    shutil.copy(ROOT / "scripts/deployment/compose-with-version.sh", deployment)
    (deployment / "prepare_host_directories.py").write_text("import sys\nsys.stdin.read()\n")
    docker_stub = """#!/bin/bash
if [[ "$*" == "compose version" || "$*" == network* ]]; then exit 0; fi
if [[ "${COYOTE3_IMAGE_TAG:-}" != "$INSTALL_TEST_EXPECTED_TAG" ]]; then
  echo "Missing or incorrect environment image tag" >&2; exit 1
fi
printf '%s\\n' "$*" >> "$INSTALL_TEST_LOG"
printf 'tag=%s\\n' "$COYOTE3_IMAGE_TAG" >> "$INSTALL_TEST_LOG"
if [[ "$*" == *"config --format json"* ]]; then cat "$INSTALL_TEST_CONFIG"; fi
if [[ "$*" == *"installation_checks state"* ]]; then
  if [[ "$INSTALL_TEST_STATE" == partial ]]; then echo "Partial installation"; exit 1; fi
  echo "$INSTALL_TEST_STATE"
fi
if [[ "$*" == *"installation_checks indexes"* && "${INSTALL_TEST_CONFLICT:-0}" == 1 ]]; then exit 1; fi
if [[ "$*" == *"installation_checks indexes-ready"* && "${INSTALL_TEST_INCOMPLETE:-0}" == 1 ]]; then exit 1; fi
"""
    binaries = tmp_path / "bin"
    binaries.mkdir()
    rendered = {
        "networks": {"app": {"name": "synthetic-network"}},
        "services": {
            "proxy": {"ports": [{"target": 8088, "published": "5815", "protocol": "tcp"}]},
            "api": {
                "environment": {
                    "COYOTE3_DB": "synthetic",
                    "IDENTITY_DB": "synthetic_identity",
                    "PUBLIC_BASE_URL": "http://synthetic.invalid:6802",
                    "SCRIPT_NAME": "/coyote3",
                }
            },
        },
    }
    config = tmp_path / "render.json"
    config.write_text(json.dumps(rendered))
    for name, body in {
        "docker": docker_stub,
        "curl": '#!/bin/bash\nprintf "curl %s\\n" "$*" >> "$INSTALL_TEST_LOG"\n',
    }.items():
        path = binaries / name
        path.write_text(body)
        path.chmod(0o700)
    environment = tmp_path / "deployment.env"
    environment.write_text("ENV_NAME=production\n")
    compose = tmp_path / "compose.yml"
    compose.write_text("services: {}\n")
    secret = tmp_path / "maintenance-uri"
    secret.write_text("mongodb://synthetic-maintenance.invalid")
    log = tmp_path / "commands"
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "INSTALL_TEST_CONFIG": str(config),
        "INSTALL_TEST_LOG": str(log),
        "INSTALL_TEST_EXPECTED_TAG": "synthetic",
    }
    for key in (
        "ENV_NAME",
        "COYOTE3_IMAGE_TAG",
        "COYOTE3_VERSION",
        "LOG_LEVEL",
        "CELERY_LOG_LEVEL",
    ):
        env.pop(key, None)
    command = [
        "bash",
        str(deployment / "install_center.sh"),
        "--env-file",
        str(environment),
        "--project",
        "synthetic",
        "--compose-file",
        str(compose),
        "--sys-admin-username",
        "synthetic.admin",
        "--sys-admin-email",
        "admin@example.test",
        "--username",
        "synthetic.emergency",
        "--email",
        "emergency@example.test",
    ]
    return command, env, log


@pytest.mark.parametrize("state", ["fresh", "existing", "partial"])
def test_bootstrap_runs_only_for_fresh_databases(fake_installation, state):
    command, env, log = fake_installation
    result = subprocess.run(
        command, env={**env, "INSTALL_TEST_STATE": state}, text=True, capture_output=True
    )
    calls = log.read_text()
    assert ("bootstrap_database.py" in calls) == (state == "fresh")
    assert ("up -d" in calls) == (state != "partial")
    assert result.returncode == (1 if state == "partial" else 0), result.stderr
    if state == "partial":
        assert "installation_checks indexes" not in calls
    if state == "fresh":
        assert "--require-empty-target" in calls
    if state != "partial":
        assert calls.index("manage_mongo_indexes.py apply") < calls.index("up -d")
        assert (
            calls.index("manage_mongo_indexes.py apply")
            < calls.index("installation_checks indexes-ready")
            < calls.index("up -d")
        )
        assert "http://127.0.0.1:5815/coyote3/api/v1/health" in calls
        assert "synthetic.invalid:6802" not in calls
    assert "mongodb://" not in calls
    assert "install_reference_data.py" not in calls
    assert "--scope knowledgebase" not in calls


@pytest.mark.parametrize(
    ("environment", "tag"),
    [
        ("production", "synthetic"),
        ("development", "synthetic-dev"),
        ("staging", "synthetic-stage"),
        ("testing", "synthetic-test"),
    ],
)
def test_installer_uses_wrapper_image_tag_for_every_compose_operation(
    fake_installation, environment, tag
):
    """Exercise the real wrapper with Docker stubbed, including initial JSON rendering."""
    command, env, log = fake_installation
    Path(command[command.index("--env-file") + 1]).write_text(f"ENV_NAME={environment}\n")
    result = subprocess.run(
        command,
        env={**env, "INSTALL_TEST_STATE": "existing", "INSTALL_TEST_EXPECTED_TAG": tag},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert f"tag={tag}" in log.read_text()
    assert "bootstrap_database.py" not in log.read_text()


@pytest.mark.parametrize("state", ["fresh", "existing"])
def test_configured_knowledgebase_uri_is_used_without_prompt(fake_installation, state):
    command, env, log = fake_installation
    command.append("--with-knowledgebase-indexes")
    result = subprocess.run(
        command,
        env={**env, "INSTALL_TEST_STATE": state},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text()
    assert "-e KNOWLEDGEBASE_MONGO_URI" not in calls
    assert "installation_checks maintenance" not in calls
    assert ("bootstrap_database.py" in calls) == (state == "fresh")
    assert "manage_mongo_indexes.py apply" in calls
    assert "up -d" in calls


def test_empty_maintenance_override_stops_before_writes(fake_installation):
    command, env, log = fake_installation
    secret = log.parent / "maintenance-uri"
    secret.write_text("")
    command += ["--knowledgebase-maintenance-uri-file", str(secret), "--with-knowledgebase-indexes"]
    result = subprocess.run(
        command, env={**env, "INSTALL_TEST_STATE": "fresh"}, capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "Maintenance URI file is empty" in result.stderr
    calls = log.read_text()
    assert "bootstrap_database.py" not in calls
    assert "manage_mongo_indexes.py apply" not in calls
    assert "up -d" not in calls


def test_index_conflict_stops_before_apply_and_start(fake_installation):
    command, env, log = fake_installation
    result = subprocess.run(
        command,
        env={**env, "INSTALL_TEST_STATE": "existing", "INSTALL_TEST_CONFLICT": "1"},
        capture_output=True,
    )
    assert result.returncode == 1
    calls = log.read_text()
    assert "bootstrap_database.py" not in calls
    assert "manage_mongo_indexes.py apply" not in calls
    assert "up -d" not in calls


def test_installer_help_and_unknown_options_do_not_run_docker():
    path = ROOT / "scripts/deployment/install_center.sh"
    assert subprocess.run(["bash", str(path), "--help"], capture_output=True).returncode == 0
    assert subprocess.run(["bash", str(path), "--unknown"], capture_output=True).returncode == 2


@pytest.mark.parametrize(
    "stage",
    ["network", "directories", "build", "validate", "bootstrap", "indexes", "start", "health"],
)
def test_each_stage_can_run_independently(fake_installation, stage):
    command, env, log = fake_installation
    result = subprocess.run(
        command + ["--steps", stage],
        env={**env, "INSTALL_TEST_STATE": "existing"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text()
    assert ("up -d" in calls) == (stage == "start")
    assert ("manage_mongo_indexes.py apply" in calls) == (stage == "indexes")
    assert ("curl " in calls) == (stage == "health")
    assert "install_reference_data.py" not in calls
    assert "--scope knowledgebase" not in calls


@pytest.mark.parametrize(
    "option, seeds, indexes",
    [("--with-knowledgebase-seeds", True, False), ("--with-knowledgebase-indexes", False, True)],
)
def test_knowledgebase_operations_are_independent_opt_ins(
    fake_installation, option, seeds, indexes
):
    command, env, log = fake_installation
    result = subprocess.run(
        command + ["--steps", "validate", option],
        env={**env, "INSTALL_TEST_STATE": "existing"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text()
    assert ("install_reference_data.py" in calls) == seeds
    assert ("--scope knowledgebase" in calls) == indexes
    assert "bootstrap_database.py" not in calls
    assert "up -d" not in calls


def test_start_cannot_bypass_missing_baseline(fake_installation):
    command, env, log = fake_installation
    result = subprocess.run(
        command + ["--steps", "start"],
        env={**env, "INSTALL_TEST_STATE": "fresh"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "baseline is missing" in result.stderr
    assert "up -d" not in log.read_text()


@pytest.mark.parametrize(
    "host_ip,published,expected_host,prefix",
    [
        ("0.0.0.0", "9123", "127.0.0.1", "/coyote3"),
        ("127.0.0.1", "7456", "127.0.0.1", ""),
        ("::", "8123", "[::1]", "/clinical"),
        ("192.0.2.10", "9555", "192.0.2.10", "/coyote3"),
    ],
)
def test_health_uses_published_proxy_port_not_public_url(
    fake_installation, host_ip, published, expected_host, prefix
):
    command, env, log = fake_installation
    config_path = Path(env["INSTALL_TEST_CONFIG"])
    config = json.loads(config_path.read_text())
    config["services"]["proxy"]["ports"] = [
        {"target": 8088, "published": published, "host_ip": host_ip}
    ]
    config["services"]["api"]["environment"].update(
        PUBLIC_BASE_URL="https://public.example.test", SCRIPT_NAME=prefix
    )
    config_path.write_text(json.dumps(config))
    result = subprocess.run(
        command + ["--steps", "health"], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text()
    assert f"http://{expected_host}:{published}{prefix}/api/v1/health" in calls
    assert "https://public.example.test" not in calls
    assert (
        f"Local application (published proxy port): http://{expected_host}:{published}{prefix}/"
        in result.stdout
    )
    assert (
        f"Public application (PUBLIC_BASE_URL): https://public.example.test{prefix}/"
        in result.stdout
    )


def test_unfinished_index_application_prevents_startup(fake_installation):
    command, env, log = fake_installation
    result = subprocess.run(
        command,
        env={**env, "INSTALL_TEST_STATE": "existing", "INSTALL_TEST_INCOMPLETE": "1"},
        capture_output=True,
    )
    assert result.returncode == 1
    calls = log.read_text()
    assert "manage_mongo_indexes.py apply" in calls
    assert "up -d" not in calls


@pytest.mark.parametrize(
    ("state", "require_present", "fails"),
    [
        ("missing", False, False),
        ("missing", True, True),
        ("present", True, False),
        ("conflict", False, True),
        ("conflict", True, True),
    ],
)
def test_index_gate_summarizes_and_closes_connections(
    monkeypatch, capsys, state, require_present, fails
):
    adapter = Mock()
    monkeypatch.setattr("scripts.database.manage_mongo_indexes._adapter", lambda scope: adapter)
    monkeypatch.setattr(
        "api.infra.mongo.index_management.build_index_plan",
        lambda _, **kwargs: [
            {
                "repository": "brca",
                "collection": "brcaexchange",
                "name": "coordinate_index",
                "state": state,
            }
        ],
    )
    if fails:
        with pytest.raises(ValueError, match="Required indexes are not ready"):
            check_indexes(require_present=require_present)
    else:
        check_indexes(require_present=require_present)
    output = capsys.readouterr().out
    assert f"{state}=1" in output
    assert ("collection=brcaexchange index=coordinate_index" in output) == fails
    adapter.close.assert_called_once()
