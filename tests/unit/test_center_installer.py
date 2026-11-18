"""Exercise installation orchestration without Docker, network or real databases."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import mongomock
import pytest

from deploy.installer.checks import (
    check_indexes,
    check_redis,
    installation_state,
    validate_maintenance_endpoint,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("environment", ["production", "stage", "dev", "test"])
def test_identity_audit_gate_is_checked_in_every_environment(monkeypatch, environment):
    """Warn-only anonymous operation does not bypass authenticated audit grant checks."""
    from deploy.installer import checks as installation_checks

    monkeypatch.setenv("ENV_NAME", environment)
    for key, value in {
        "COYOTE4_MONGO_URI": "mongodb://synthetic.invalid/?replicaSet=synthetic",
        "IDENTITY_MONGO_URI": "",
        "KNOWLEDGEBASE_MONGO_URI": "",
        "BAM_MONGO_URI": "",
        "COYOTE4_DB": "synthetic_app",
        "IDENTITY_DB": "synthetic_identity",
        "KNOWLEDGEBASE_DB": "synthetic_kb",
        "BAM_DB": "synthetic_bam",
    }.items():
        monkeypatch.setenv(key, value)
    client = MagicMock()
    client.admin.command.return_value = {"isWritablePrimary": True, "setName": "synthetic"}
    connection = MagicMock()
    connection.__enter__.return_value = client
    monkeypatch.setattr(installation_checks, "MongoClient", Mock(return_value=connection))
    verify = Mock(side_effect=ValueError("Runtime authentication required"))
    monkeypatch.setattr(installation_checks, "verify_runtime_audit_permissions", verify)
    with pytest.raises(ValueError, match="Runtime authentication required"):
        installation_checks.check_endpoints()
    verify.assert_called_once_with(client["synthetic_identity"].client, "synthetic_identity")


def test_redis_gate_checks_all_three_endpoints(monkeypatch):
    """Cache, broker and results must all accept an authenticated PING."""
    factory = Mock()
    client = factory.return_value.__enter__ = Mock(return_value=Mock())
    factory.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("redis.Redis.from_url", factory)
    for index, key in enumerate(("CACHE_REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND")):
        monkeypatch.setenv(key, f"redis://synthetic.invalid/{index}")
    check_redis()
    assert factory.call_count == 3
    assert client.return_value.ping.call_count == 3


def test_redis_gate_redacts_driver_details(monkeypatch):
    """Driver errors must not disclose credentials in deployment output."""
    monkeypatch.setenv("CACHE_REDIS_URL", "redis://:private@synthetic.invalid/0")
    monkeypatch.setattr("redis.Redis.from_url", Mock(side_effect=TimeoutError("private")))
    with pytest.raises(ValueError, match="CACHE_REDIS_URL PING failed") as error:
        check_redis()
    assert "private" not in str(error.value)


def test_redis_gate_rejects_missing_celery_transport_dependency_before_ping(monkeypatch):
    """A Redis client PING cannot hide a broken Celery Redis transport installation."""
    factory = Mock()
    monkeypatch.setattr("redis.Redis.from_url", factory)
    monkeypatch.setattr(
        "kombu.transport.get_transport_cls",
        Mock(side_effect=ModuleNotFoundError("No module named 'packaging'", name="packaging")),
    )
    with pytest.raises(
        ValueError, match=r"Celery Redis transport cannot load \(missing packaging\)"
    ):
        check_redis()
    factory.assert_not_called()


def test_redis_failure_stops_before_bootstrap_or_application_start(fake_installation):
    """Unreachable external Redis blocks application writes without starting a server."""
    command, env, log = fake_installation
    result = subprocess.run(
        command,
        env={**env, "INSTALL_TEST_STATE": "fresh", "INSTALL_TEST_REDIS_FAILURE": "1"},
        capture_output=True,
    )
    assert result.returncode == 1
    calls = log.read_text() if log.exists() else ""
    assert "deploy.installer.checks redis" in calls
    assert not any("up " in line and "redis" in line for line in calls.splitlines())
    assert "bootstrap_database.py" not in calls
    assert "manage_mongo_indexes.py apply" not in calls
    assert "up -d --no-build --wait" not in calls


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


def test_complete_initial_accounts_allow_start_before_authenticated_catalog_installation():
    client = mongomock.MongoClient()
    client.identity.users.insert_many([{"roles": ["superuser"]}, {"roles": ["sys_admin"]}])
    client.identity.roles.insert_one({"role_id": "superuser"})
    client.identity.permissions.insert_one({"permission_id": "synthetic"})
    assert installation_state(client.application, client.identity) == "existing"
    assert client.application.list_collection_names() == []


def test_maintenance_credentials_cannot_redirect_knowledgebase(monkeypatch):
    for key, value in {
        "COYOTE4_MONGO_URI": "mongodb://reader@synthetic.invalid/?replicaSet=example",
        "COYOTE4_DB": "application",
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
    deployment = tmp_path / "deploy/installer"
    shutil.copytree(
        ROOT / "deploy/installer", deployment, ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copy(ROOT / "install.sh", tmp_path)
    (tmp_path / "release.toml").write_text('application_version="synthetic"\n')
    release_scripts = tmp_path / "scripts/release"
    release_scripts.mkdir(parents=True)
    shutil.copy(ROOT / "scripts/release/build_sdk.py", release_scripts)
    (release_scripts / "verify_sdk_artifact.py").write_text(
        "import os\n"
        "def verify_compose_artifacts(*args):\n"
        "    with open(os.environ['INSTALL_TEST_LOG'], 'a') as log:\n"
        "        log.write('sdk-artifact-preflight\\n')\n"
        "    if os.environ.get('INSTALL_TEST_ARTIFACT_FAILURE') == '1':\n"
        "        raise ValueError('Synthetic artifact failure')\n"
    )
    (deployment / "storage.py").write_text("def prepare(config): pass\n")
    docker_stub = """#!/bin/bash
if [[ "$*" == "compose version" ]]; then exit 0; fi
if [[ "$1" == network ]]; then
  printf '%s\\n' "$*" >> "$INSTALL_TEST_LOG"
  if [[ "$2" != inspect ]]; then echo "Network mutation forbidden" >&2; exit 99; fi
  if [[ "${INSTALL_TEST_NETWORK_MISSING:-0}" == 1 ]]; then exit 1; fi
  echo "${INSTALL_TEST_NETWORK_DRIVER:-bridge}"
  exit 0
fi
if [[ "${COYOTE4_IMAGE_TAG:-}" != "$INSTALL_TEST_EXPECTED_TAG" ]]; then
  echo "Missing or incorrect environment image tag" >&2; exit 1
fi
printf '%s\\n' "$*" >> "$INSTALL_TEST_LOG"
printf 'tag=%s\\n' "$COYOTE4_IMAGE_TAG" >> "$INSTALL_TEST_LOG"
printf 'commit=%s\\n' "$GIT_COMMIT" >> "$INSTALL_TEST_LOG"
if [[ "$*" == *"config --format json"* ]]; then cat "$INSTALL_TEST_CONFIG"; fi
if [[ "$*" == *"deploy.installer.checks state"* ]]; then
  if [[ "$INSTALL_TEST_STATE" == partial ]]; then echo "Partial installation"; exit 1; fi
  echo "$INSTALL_TEST_STATE"
fi
if [[ "$*" == *"deploy.installer.checks indexes"* && "${INSTALL_TEST_CONFLICT:-0}" == 1 ]]; then exit 1; fi
if [[ "$*" == *"deploy.installer.checks indexes-ready"* && "${INSTALL_TEST_INCOMPLETE:-0}" == 1 ]]; then exit 1; fi
if [[ "$*" == *"deploy.installer.checks redis"* && "${INSTALL_TEST_REDIS_FAILURE:-0}" == 1 ]]; then exit 1; fi
if [[ "$*" == *"manage_mongo_roles"* && "${INSTALL_TEST_IDENTITY_FAILURE:-0}" == 1 ]]; then exit 1; fi
"""
    binaries = tmp_path / "bin"
    binaries.mkdir()
    rendered = {
        "networks": {"app": {"name": "synthetic-network", "external": True}},
        "services": {
            "proxy": {"ports": [{"target": 8088, "published": "5815", "protocol": "tcp"}]},
            "api": {
                "environment": {
                    "COYOTE4_DB": "synthetic",
                    "IDENTITY_DB": "synthetic_identity",
                    "ENV_NAME": "production",
                    "COYOTE4_MONGO_URI": "mongodb://synthetic-runtime:synthetic-secret@synthetic.invalid/?authSource=admin",
                    "PUBLIC_BASE_URL": "http://synthetic.invalid:6802",
                    "SCRIPT_NAME": "/coyote4",
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
    secrets = {
        "SECRET_KEY": "synthetic-secret-key",
        "INTERNAL_API_TOKEN": "synthetic-token-value",
        "PASSWORD_TOKEN_SALT": "synthetic-token-salt",
        "REDIS_PASSWORD": "a" * 32,
        "CACHE_REDIS_URL": "redis://:synthetic_redis_password@127.0.0.1:6379/0",
        "CELERY_BROKER_URL": "redis://:synthetic_redis_password@127.0.0.1:6379/1",
        "CELERY_RESULT_BACKEND": "redis://:synthetic_redis_password@127.0.0.1:6379/2",
        "COYOTE4_MONGO_URI": "mongodb://synthetic.invalid",
    }
    rendered["services"]["api"]["environment"].update(secrets)
    config.write_text(json.dumps(rendered))
    environment.write_text(
        "ENV_NAME=production\n" + "".join(f"{key}={value}\n" for key, value in secrets.items())
    )
    compose = tmp_path / "compose.yml"
    compose.write_text("services: {}\n")
    secret = tmp_path / "maintenance-uri"
    secret.write_text("mongodb://synthetic-maintenance.invalid")
    secret.chmod(0o600)
    log = tmp_path / "commands"
    env = {
        **os.environ,
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "INSTALL_TEST_CONFIG": str(config),
        "INSTALL_TEST_LOG": str(log),
        "INSTALL_TEST_EXPECTED_TAG": "synthetic",
        "GIT_COMMIT": "a" * 40,
        "PYTHON_BIN": sys.executable,
    }
    for key in (
        "ENV_NAME",
        "COYOTE4_IMAGE_TAG",
        "COYOTE4_VERSION",
        "LOG_LEVEL",
        "CELERY_LOG_LEVEL",
    ):
        env.pop(key, None)
    command = [
        "bash",
        str(tmp_path / "install.sh"),
        "deploy",
        "--env-file",
        str(environment),
        "--project",
        "synthetic",
        "--compose-file",
        str(compose),
        "--system-admin-username",
        "coyote4.sysadmin",
        "--system-admin-email",
        "admin@example.test",
        "--superuser-username",
        "coyote4.superuser",
        "--superuser-email",
        "emergency@example.test",
    ]
    return command, env, log


@pytest.mark.parametrize(
    "environment,shared_uri,identity_uri",
    [
        ("production", "mongodb://synthetic.invalid", ""),
        (
            "stage",
            "mongodb://synthetic:private-value@synthetic.invalid",
            "mongodb://identity.invalid",
        ),
        (
            "production",
            "mongodb://synthetic.invalid",
            "mongodb://runtime:private-value@identity.invalid",
        ),
        ("production", "mongodb://runtime:private-value@synthetic.invalid", ""),
        ("production", "mongodb://synthetic.invalid/?authMechanism=MONGODB-X509", ""),
        ("dev", "mongodb://synthetic.invalid", ""),
        ("test", "mongodb://synthetic.invalid", ""),
    ],
)
def test_anonymous_identity_does_not_block_installation(
    fake_installation, environment, shared_uri, identity_uri
):
    """Both anonymous and authenticated connections reach the read-only endpoint checks."""
    command, env, log = fake_installation
    path = Path(env["INSTALL_TEST_CONFIG"])
    config = json.loads(path.read_text())
    config["services"]["api"]["environment"].update(
        ENV_NAME=environment, COYOTE4_MONGO_URI=shared_uri, IDENTITY_MONGO_URI=identity_uri
    )
    path.write_text(json.dumps(config))
    result = subprocess.run(
        command, env={**env, "INSTALL_TEST_STATE": "existing"}, text=True, capture_output=True
    )
    assert result.returncode == 0, result.stderr
    assert "private-value" not in result.stdout + result.stderr
    assert "deploy.installer.checks state" in (log.read_text() if log.exists() else "")


@pytest.mark.parametrize("failure", [False, True])
def test_identity_role_upgrade_runs_before_state_validation_and_stops_on_failure(
    fake_installation, failure
):
    """The one-command installer uses ephemeral credentials without logging their URI."""
    command, env, log = fake_installation
    secret = Path(env["INSTALL_TEST_CONFIG"]).parent / "identity-maintenance-uri"
    uri = "mongodb://synthetic-identity-maintenance.invalid"
    secret.write_text(uri)
    secret.chmod(0o600)
    result = subprocess.run(
        [
            *command,
            "--skip-build",
            "--steps",
            "validate",
            "--identity-maintenance-uri-file",
            str(secret),
        ],
        env={
            **env,
            "INSTALL_TEST_STATE": "existing",
            "INSTALL_TEST_IDENTITY_FAILURE": "1" if failure else "0",
        },
        capture_output=True,
        text=True,
    )
    calls = log.read_text() if log.exists() else ""
    assert "--maintenance-uri-env COYOTE_INSTALL_IDENTITY_URI --apply" in calls
    assert uri not in calls + result.stdout + result.stderr
    if failure:
        assert result.returncode != 0
        assert "deploy.installer.checks state" not in calls
    else:
        assert result.returncode == 0, result.stderr
        assert calls.index("manage_mongo_roles") < calls.index("deploy.installer.checks state")


def test_empty_identity_maintenance_file_stops_before_role_or_state_operations(fake_installation):
    command, env, log = fake_installation
    secret = Path(env["INSTALL_TEST_CONFIG"]).parent / "empty-identity-uri"
    secret.write_text("")
    secret.chmod(0o600)
    result = subprocess.run(
        [
            *command,
            "--skip-build",
            "--steps",
            "validate",
            "--identity-maintenance-uri-file",
            str(secret),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Maintenance URI file must contain one nonempty URI" in result.stderr
    assert "manage_mongo_roles" not in (log.read_text() if log.exists() else "")
    assert "deploy.installer.checks state" not in (log.read_text() if log.exists() else "")


def test_missing_sdk_artifact_stops_before_installation_stages(fake_installation):
    """An invalid build input cannot trigger storage, network or database operations."""
    command, env, log = fake_installation
    result = subprocess.run(
        command,
        env={**env, "INSTALL_TEST_ARTIFACT_FAILURE": "1"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    calls = log.read_text() if log.exists() else ""
    assert calls.endswith("sdk-artifact-preflight\n")
    assert "network inspect" not in calls
    assert " build" not in calls
    assert " run " not in calls
    assert " up " not in calls


def test_skip_build_does_not_require_local_sdk_artifact(fake_installation):
    """An installation using existing images does not need wheel build inputs."""
    command, env, log = fake_installation
    result = subprocess.run(
        [*command, "--skip-build", "--steps", "network"],
        env={**env, "INSTALL_TEST_ARTIFACT_FAILURE": "1"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "sdk-artifact-preflight" not in (log.read_text() if log.exists() else "")


@pytest.mark.parametrize("explicit", [False, True])
def test_installer_defaults_commit_without_overwriting_explicit_value(fake_installation, explicit):
    """Source provenance is available to Compose in a fresh operator shell."""
    command, env, log = fake_installation
    binary = Path(env["PATH"].split(os.pathsep)[0]) / "git"
    binary.write_text('#!/bin/bash\nprintf "%s\\n" "' + "b" * 40 + '"\n')
    binary.chmod(0o700)
    if not explicit:
        env.pop("GIT_COMMIT")
    result = subprocess.run(
        [*command, "--steps", "network"], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert f"commit={('a' if explicit else 'b') * 40}\n" in (
        log.read_text() if log.exists() else ""
    )


@pytest.mark.parametrize("stage", [None, "network", "validate", "bootstrap", "indexes", "start"])
@pytest.mark.parametrize("failure", ["missing", "host"])
def test_network_failure_stops_before_build_or_container_operations(
    fake_installation, stage, failure
):
    """Missing or unsuitable infrastructure cannot trigger implicit network provisioning."""
    command, env, log = fake_installation
    if stage:
        command += ["--steps", stage]
    env.update(INSTALL_TEST_NETWORK_MISSING="1" if failure == "missing" else "0")
    env["INSTALL_TEST_NETWORK_DRIVER"] = failure
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert "network" in result.stderr.lower()
    calls = (log.read_text() if log.exists() else "").splitlines()
    assert calls[-1] == "network inspect synthetic-network --format {{.Driver}}"
    assert not any(" build" in call or " run " in call or " up " in call for call in calls)


def test_compose_managed_network_is_rejected_before_network_or_container_operations(
    fake_installation,
):
    """An overlay cannot let Compose create the application network implicitly."""
    command, env, log = fake_installation
    config_path = Path(env["INSTALL_TEST_CONFIG"])
    config = json.loads(config_path.read_text())
    config["networks"]["app"]["external"] = False
    config_path.write_text(json.dumps(config))
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Application network must be external" in result.stderr
    calls = log.read_text() if log.exists() else ""
    assert "network inspect" not in calls
    assert " run " not in calls
    assert " up " not in calls


@pytest.mark.parametrize(
    "flags",
    [["--with-knowledgebase-indexes"], ["--knowledgebase-maintenance-uri-file"]],
)
def test_maintenance_container_operations_also_require_existing_network(fake_installation, flags):
    """Independent maintenance checks cannot bypass the external network gate."""
    command, env, log = fake_installation
    if flags == ["--knowledgebase-maintenance-uri-file"]:
        flags = [*flags, str(log.parent / "maintenance-uri")]
    result = subprocess.run(
        command + ["--steps", "build", *flags],
        env={**env, "INSTALL_TEST_NETWORK_MISSING": "1"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "network" in result.stderr.lower()
    calls = log.read_text() if log.exists() else ""
    assert " build" not in calls
    assert " run " not in calls


@pytest.mark.parametrize("state", ["fresh", "existing", "partial"])
def test_bootstrap_runs_only_for_fresh_databases(fake_installation, state):
    command, env, log = fake_installation
    result = subprocess.run(
        command, env={**env, "INSTALL_TEST_STATE": state}, text=True, capture_output=True
    )
    calls = log.read_text() if log.exists() else ""
    assert ("bootstrap_database.py" in calls) == (state == "fresh")
    assert ("up -d --no-build --wait" in calls) == (state != "partial")
    assert result.returncode == (1 if state == "partial" else 0), result.stderr
    if state == "partial":
        assert "deploy.installer.checks indexes" not in calls
    if state == "fresh":
        assert "--require-empty-target" in calls
        assert "--system-admin-username coyote4.sysadmin" in calls
        assert "--system-admin-email admin@example.test" in calls
        assert "--superuser-username coyote4.superuser" in calls
        assert "--superuser-email emergency@example.test" in calls
    if state != "partial":
        assert calls.index("manage_mongo_indexes.py apply") < calls.index("up -d --no-build --wait")
        assert (
            calls.index("manage_mongo_indexes.py apply")
            < calls.index("deploy.installer.checks indexes-ready")
            < calls.index("up -d --no-build --wait")
        )
        assert "http://127.0.0.1:5815/coyote4/api/v1/health" in calls
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
    env_path = Path(command[command.index("--env-file") + 1])
    env_path.write_text(
        env_path.read_text().replace("ENV_NAME=production", f"ENV_NAME={environment}")
    )
    result = subprocess.run(
        command,
        env={**env, "INSTALL_TEST_STATE": "existing", "INSTALL_TEST_EXPECTED_TAG": tag},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert f"tag={tag}" in (log.read_text() if log.exists() else "")
    assert "bootstrap_database.py" not in (log.read_text() if log.exists() else "")


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
    calls = log.read_text() if log.exists() else ""
    assert "-e KNOWLEDGEBASE_MONGO_URI" not in calls
    assert "deploy.installer.checks maintenance" not in calls
    assert ("bootstrap_database.py" in calls) == (state == "fresh")
    assert "manage_mongo_indexes.py apply" in calls
    assert "up -d" in calls


def test_empty_maintenance_override_stops_before_writes(fake_installation):
    command, env, log = fake_installation
    secret = log.parent / "maintenance-uri"
    secret.write_text("")
    secret.chmod(0o600)
    command += ["--knowledgebase-maintenance-uri-file", str(secret), "--with-knowledgebase-indexes"]
    result = subprocess.run(
        command, env={**env, "INSTALL_TEST_STATE": "fresh"}, capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Maintenance URI file must contain one nonempty URI" in result.stderr
    calls = log.read_text() if log.exists() else ""
    assert "bootstrap_database.py" not in calls
    assert "manage_mongo_indexes.py apply" not in calls
    assert "up -d --no-build --wait" not in calls


def test_index_conflict_stops_before_apply_and_start(fake_installation):
    command, env, log = fake_installation
    result = subprocess.run(
        command,
        env={**env, "INSTALL_TEST_STATE": "existing", "INSTALL_TEST_CONFLICT": "1"},
        capture_output=True,
    )
    assert result.returncode == 1
    calls = log.read_text() if log.exists() else ""
    assert "bootstrap_database.py" not in calls
    assert "manage_mongo_indexes.py apply" not in calls
    assert "up -d --no-build --wait" not in calls


def test_installer_help_and_unknown_options_do_not_run_docker():
    path = ROOT / "install.sh"
    assert subprocess.run(["bash", str(path), "--help"], capture_output=True).returncode == 0
    assert subprocess.run(["bash", str(path), "--unknown"], capture_output=True).returncode == 2


@pytest.mark.parametrize(
    "flags",
    [
        ["--skip-knowledgebase"],
        ["--skip-application"],
        ["--skip-users", "--skip-application", "--skip-knowledgebase"],
    ],
)
def test_fresh_module_skip_flags_are_passed_to_bootstrap(fake_installation, flags):
    command, env, log = fake_installation
    result = subprocess.run(
        command + flags, env={**env, "INSTALL_TEST_STATE": "fresh"}, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    invocation = next(
        row
        for row in (log.read_text() if log.exists() else "").splitlines()
        if "bootstrap_database.py" in row
    )
    for flag in flags:
        assert flag in invocation


@pytest.mark.parametrize(
    "flags",
    [
        ["--skip-users"],
        ["--skip-demo"],
        ["--force"],
        ["--with-demo-center"],
        ["--with-knowledgebase-seeds"],
    ],
)
def test_unsafe_or_retired_installation_options_stop_before_docker(fake_installation, flags):
    command, env, log = fake_installation
    result = subprocess.run(command + flags, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not log.exists()


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
    calls = log.read_text() if log.exists() else ""
    assert ("up -d" in calls) == (stage == "start")
    assert ("manage_mongo_indexes.py apply" in calls) == (stage == "indexes")
    assert ("curl " in calls) == (stage == "health")
    assert ("network inspect" in calls) == (
        stage in {"network", "validate", "bootstrap", "indexes", "start"}
    )
    assert "deploy.installer.data" not in calls
    assert "--scope knowledgebase" not in calls


def test_knowledgebase_indexes_remain_an_independent_maintenance_operation(fake_installation):
    command, env, log = fake_installation
    result = subprocess.run(
        command + ["--steps", "validate", "--with-knowledgebase-indexes"],
        env={**env, "INSTALL_TEST_STATE": "existing"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text() if log.exists() else ""
    assert "manage_mongo_indexes.py apply --scope knowledgebase" in calls
    assert "bootstrap_database.py" not in calls
    assert "up -d --no-build --wait" not in calls
    assert "deploy.installer.data --" not in calls


def test_start_cannot_bypass_missing_baseline(fake_installation):
    command, env, log = fake_installation
    result = subprocess.run(
        command + ["--steps", "start"],
        env={**env, "INSTALL_TEST_STATE": "fresh"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Initial accounts are missing" in result.stderr
    assert "up -d --no-build --wait" not in (log.read_text() if log.exists() else "")


@pytest.mark.parametrize(
    "host_ip,published,expected_host,prefix",
    [
        ("0.0.0.0", "9123", "127.0.0.1", "/coyote4"),
        ("127.0.0.1", "7456", "127.0.0.1", ""),
        ("::", "8123", "[::1]", "/clinical"),
        ("192.0.2.10", "9555", "192.0.2.10", "/coyote4"),
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
    calls = log.read_text() if log.exists() else ""
    assert f"http://{expected_host}:{published}{prefix}/api/v1/health" in calls
    assert "https://public.example.test" not in calls
    assert (
        f"Local application (published proxy port): http://{expected_host}:{published}{prefix}/"
        in result.stderr
    )
    assert (
        f"Public application (PUBLIC_BASE_URL): https://public.example.test{prefix}/"
        in result.stderr
    )


def test_unfinished_index_application_prevents_startup(fake_installation):
    command, env, log = fake_installation
    result = subprocess.run(
        command,
        env={**env, "INSTALL_TEST_STATE": "existing", "INSTALL_TEST_INCOMPLETE": "1"},
        capture_output=True,
    )
    assert result.returncode == 1
    calls = log.read_text() if log.exists() else ""
    assert "manage_mongo_indexes.py apply" in calls
    assert "up -d --no-build --wait" not in calls


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
        "coyote_mongo.index_management.build_index_plan",
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
