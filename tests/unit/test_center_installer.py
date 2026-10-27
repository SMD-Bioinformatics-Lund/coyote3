"""Exercise installation orchestration without Docker, network or real databases."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock

import mongomock
import pytest

from scripts.deployment.installation_checks import (
    check_indexes,
    check_redis,
    installation_state,
    validate_maintenance_endpoint,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("environment", ["production", "stage", "dev", "test"])
def test_identity_audit_gate_is_checked_in_every_environment(monkeypatch, environment):
    """Warn-only anonymous operation does not bypass authenticated audit grant checks."""
    from scripts.deployment import installation_checks

    monkeypatch.setenv("ENV_NAME", environment)
    for key, value in {
        "COYOTE3_MONGO_URI": "mongodb://synthetic.invalid/?replicaSet=synthetic",
        "IDENTITY_MONGO_URI": "",
        "KNOWLEDGEBASE_MONGO_URI": "",
        "BAM_MONGO_URI": "",
        "COYOTE3_DB": "synthetic_app",
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


def test_redis_failure_stops_before_bootstrap_or_application_start(fake_installation):
    """A healthy Redis container alone cannot authorize installation writes or startup."""
    command, env, log = fake_installation
    result = subprocess.run(
        command,
        env={**env, "INSTALL_TEST_STATE": "fresh", "INSTALL_TEST_REDIS_FAILURE": "1"},
        capture_output=True,
    )
    assert result.returncode == 1
    calls = log.read_text()
    assert calls.index("--wait-timeout 60 redis") < calls.index("installation_checks redis")
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
    shutil.copy(ROOT / "scripts/deployment/python_runtime.sh", deployment)
    (tmp_path / "api").mkdir(parents=True)
    (tmp_path / "api/version.py").write_text('print("synthetic")\n')
    (deployment / "validate_env_secrets.sh").write_text("#!/bin/bash\nexit 0\n")
    shutil.copy(ROOT / "scripts/deployment/compose-with-version.sh", deployment)
    release_scripts = tmp_path / "scripts/release"
    release_scripts.mkdir()
    (release_scripts / "verify_sdk_artifact.py").write_text(
        "import os, sys\n"
        "with open(os.environ['INSTALL_TEST_LOG'], 'a') as log:\n"
        "    log.write('sdk-artifact-preflight\\n')\n"
        "sys.exit(int(os.environ.get('INSTALL_TEST_ARTIFACT_FAILURE', '0')))\n"
    )
    (deployment / "prepare_host_directories.py").write_text("import sys\nsys.stdin.read()\n")
    docker_stub = """#!/bin/bash
if [[ "$*" == "compose version" ]]; then exit 0; fi
if [[ "$1" == network ]]; then
  printf '%s\\n' "$*" >> "$INSTALL_TEST_LOG"
  if [[ "$2" != inspect ]]; then echo "Network mutation forbidden" >&2; exit 99; fi
  if [[ "${INSTALL_TEST_NETWORK_MISSING:-0}" == 1 ]]; then exit 1; fi
  echo "${INSTALL_TEST_NETWORK_DRIVER:-bridge}"
  exit 0
fi
if [[ "${COYOTE3_IMAGE_TAG:-}" != "$INSTALL_TEST_EXPECTED_TAG" ]]; then
  echo "Missing or incorrect environment image tag" >&2; exit 1
fi
printf '%s\\n' "$*" >> "$INSTALL_TEST_LOG"
printf 'tag=%s\\n' "$COYOTE3_IMAGE_TAG" >> "$INSTALL_TEST_LOG"
printf 'commit=%s\\n' "$GIT_COMMIT" >> "$INSTALL_TEST_LOG"
if [[ "$*" == *"config --format json"* ]]; then cat "$INSTALL_TEST_CONFIG"; fi
if [[ "$*" == *"installation_checks state"* ]]; then
  if [[ "$INSTALL_TEST_STATE" == partial ]]; then echo "Partial installation"; exit 1; fi
  echo "$INSTALL_TEST_STATE"
fi
if [[ "$*" == *"installation_checks indexes"* && "${INSTALL_TEST_CONFLICT:-0}" == 1 ]]; then exit 1; fi
if [[ "$*" == *"installation_checks indexes-ready"* && "${INSTALL_TEST_INCOMPLETE:-0}" == 1 ]]; then exit 1; fi
if [[ "$*" == *"installation_checks redis"* && "${INSTALL_TEST_REDIS_FAILURE:-0}" == 1 ]]; then exit 1; fi
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
                    "COYOTE3_DB": "synthetic",
                    "IDENTITY_DB": "synthetic_identity",
                    "ENV_NAME": "production",
                    "COYOTE3_MONGO_URI": "mongodb://synthetic-runtime:synthetic-secret@synthetic.invalid/?authSource=admin",
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
        "GIT_COMMIT": "a" * 40,
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
        "coyote3.sysadmin",
        "--sys-admin-email",
        "admin@example.test",
        "--username",
        "coyote3.superuser",
        "--email",
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
        ENV_NAME=environment, COYOTE3_MONGO_URI=shared_uri, IDENTITY_MONGO_URI=identity_uri
    )
    path.write_text(json.dumps(config))
    result = subprocess.run(
        command, env={**env, "INSTALL_TEST_STATE": "existing"}, text=True, capture_output=True
    )
    assert result.returncode == 0, result.stderr
    assert "private-value" not in result.stdout + result.stderr
    assert "installation_checks state" in log.read_text()


@pytest.mark.parametrize("failure", [False, True])
def test_identity_role_upgrade_runs_before_state_validation_and_stops_on_failure(
    fake_installation, failure
):
    """The one-command installer uses ephemeral credentials without logging their URI."""
    command, env, log = fake_installation
    secret = Path(env["INSTALL_TEST_CONFIG"]).parent / "identity-maintenance-uri"
    uri = "mongodb://synthetic-identity-maintenance.invalid"
    secret.write_text(uri)
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
    calls = log.read_text()
    assert "--maintenance-uri-env COYOTE_INSTALL_IDENTITY_URI --apply" in calls
    assert uri not in calls + result.stdout + result.stderr
    if failure:
        assert result.returncode != 0
        assert "installation_checks state" not in calls
    else:
        assert result.returncode == 0, result.stderr
        assert calls.index("manage_mongo_roles") < calls.index("installation_checks state")


def test_empty_identity_maintenance_file_stops_before_role_or_state_operations(fake_installation):
    command, env, log = fake_installation
    secret = Path(env["INSTALL_TEST_CONFIG"]).parent / "empty-identity-uri"
    secret.write_text("")
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
    assert result.returncode == 2
    assert "Identity maintenance URI file is empty" in result.stderr
    assert "manage_mongo_roles" not in log.read_text()
    assert "installation_checks state" not in log.read_text()


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
    calls = log.read_text()
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
    assert "sdk-artifact-preflight" not in log.read_text()


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
    assert f"commit={('a' if explicit else 'b') * 40}\n" in log.read_text()


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
    assert "No host networking changes were attempted" in result.stderr
    calls = log.read_text().splitlines()
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
    calls = log.read_text()
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
    assert "No host networking changes were attempted" in result.stderr
    calls = log.read_text()
    assert " build" not in calls
    assert " run " not in calls


@pytest.mark.parametrize("state", ["fresh", "existing", "partial"])
def test_bootstrap_runs_only_for_fresh_databases(fake_installation, state):
    command, env, log = fake_installation
    result = subprocess.run(
        command, env={**env, "INSTALL_TEST_STATE": state}, text=True, capture_output=True
    )
    calls = log.read_text()
    assert ("bootstrap_database.py" in calls) == (state == "fresh")
    assert ("up -d --no-build --wait" in calls) == (state != "partial")
    assert result.returncode == (1 if state == "partial" else 0), result.stderr
    if state == "partial":
        assert "installation_checks indexes" not in calls
    if state == "fresh":
        assert "--require-empty-target" in calls
    if state != "partial":
        assert calls.index("manage_mongo_indexes.py apply") < calls.index("up -d --no-build --wait")
        assert (
            calls.index("manage_mongo_indexes.py apply")
            < calls.index("installation_checks indexes-ready")
            < calls.index("up -d --no-build --wait")
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
    assert "up -d --no-build --wait" not in calls


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
    assert "up -d --no-build --wait" not in calls


def test_installer_help_and_unknown_options_do_not_run_docker():
    path = ROOT / "scripts/deployment/install_center.sh"
    assert subprocess.run(["bash", str(path), "--help"], capture_output=True).returncode == 0
    assert subprocess.run(["bash", str(path), "--unknown"], capture_output=True).returncode == 2


@pytest.mark.parametrize("state", ["fresh", "existing", "partial"])
def test_setup_center_defaults_to_complete_bootstrap_only_when_fresh(fake_installation, state):
    """All default seed modules run inside initial bootstrap, never during redeployment."""
    command, env, log = fake_installation
    result = subprocess.run(
        command + ["--setup-center"],
        env={**env, "INSTALL_TEST_STATE": state},
        capture_output=True,
        text=True,
    )
    calls = log.read_text()
    assert result.returncode == (1 if state == "partial" else 0), result.stderr
    assert ("bootstrap_database.py" in calls) == (state == "fresh")
    assert ("up -d --no-build --wait" in calls) == (state != "partial")
    assert "install_reference_data.py" not in calls
    assert "install_demo_starter" not in calls
    assert "manage_data.py --" not in calls
    assert "--skip-demo" not in calls
    assert "--skip-knowledgebase" not in calls


@pytest.mark.parametrize(
    "flags",
    [
        ["--skip-demo"],
        ["--skip-knowledgebase"],
        ["--skip-application", "--skip-demo"],
        ["--skip-users", "--skip-application", "--skip-knowledgebase", "--skip-demo"],
    ],
)
def test_fresh_module_skip_flags_are_passed_to_bootstrap(fake_installation, flags):
    command, env, log = fake_installation
    result = subprocess.run(
        command + flags, env={**env, "INSTALL_TEST_STATE": "fresh"}, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    invocation = next(row for row in log.read_text().splitlines() if "bootstrap_database.py" in row)
    for flag in flags:
        assert flag in invocation


@pytest.mark.parametrize(
    "flags",
    [
        ["--skip-users"],
        ["--skip-application"],
        ["--force"],
        ["--with-demo-center"],
        ["--with-knowledgebase-seeds"],
    ],
)
def test_unsafe_or_retired_installation_options_stop_before_docker(fake_installation, flags):
    command, env, log = fake_installation
    result = subprocess.run(command + flags, env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert not log.exists()


@pytest.mark.parametrize(
    "flags", [["--setup-center", "--steps", "health"], ["--steps", "health", "--setup-center"]]
)
def test_setup_center_rejects_partial_stage_selection_before_docker(fake_installation, flags):
    """Reject ambiguous setup requests consistently regardless of argument order."""
    command, env, log = fake_installation
    result = subprocess.run(command + flags, env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert "cannot be combined" in result.stderr
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
    calls = log.read_text()
    assert ("up -d" in calls) == (stage == "start")
    assert ("manage_mongo_indexes.py apply" in calls) == (stage == "indexes")
    assert ("curl " in calls) == (stage == "health")
    assert ("network inspect" in calls) == (
        stage in {"network", "validate", "bootstrap", "indexes", "start"}
    )
    assert "manage_data.py" not in calls
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
    calls = log.read_text()
    assert "manage_mongo_indexes.py apply --scope knowledgebase" in calls
    assert "bootstrap_database.py" not in calls
    assert "up -d --no-build --wait" not in calls
    assert "manage_data.py --" not in calls


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
    assert "up -d --no-build --wait" not in log.read_text()


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
