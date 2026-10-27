"""Check deployment commands against synthetic Compose output without starting services."""

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.deployment import installation_checks

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("length,valid", [(15, False), (16, True), (64, True)])
def test_deployment_secret_minimum_is_sixteen_characters(tmp_path, length, valid):
    """All four independent secrets accept URL-safe 16-character values, including Redis."""
    environment = tmp_path / "synthetic.env"
    environment.write_text(
        "\n".join(
            [
                f"{name}='{'z' * length}'"
                for name in (
                    "SECRET_KEY",
                    "INTERNAL_API_TOKEN",
                    "PASSWORD_TOKEN_SALT",
                    "REDIS_PASSWORD",
                )
            ]
            + ["COYOTE3_MONGO_URI='mongodb://127.0.0.1:27017/'"]
        )
    )
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/deployment/validate_env_secrets.sh"),
            "--env-file",
            str(environment),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is valid
    assert ("at least 16 characters" in result.stdout) is not valid


def test_configuration_gate_reports_field_errors_without_echoing_input(monkeypatch, capsys):
    """Operators need the failing setting, not a dump of the submitted input value."""
    from coyote3.application.reporting.presentation import ReportPresentation

    def invalid_configuration():
        """Raise a representative optional center-file validation error."""
        ReportPresentation.model_validate({"empty_results": {"SNVV": "synthetic-private-input"}})

    monkeypatch.setattr(installation_checks, "validate_configuration", invalid_configuration)
    monkeypatch.setattr(sys, "argv", ["installation_checks", "configuration"])
    assert installation_checks.main() == 1
    output = capsys.readouterr().out
    assert "SNVV" in output
    assert "synthetic-private-input" not in output


@pytest.fixture
def deployment(tmp_path):
    """Provide private synthetic configuration and a Docker stub with no network access."""
    center = tmp_path / "center"
    shutil.copytree(ROOT / "config/examples/center", center)
    roots = {}
    for name in ("data", "logs"):
        roots[name] = tmp_path / name
        roots[name].mkdir()
    settings = {
        "ENV_NAME": "production",
        "SECRET_KEY": "synthetic-secret-key",
        "INTERNAL_API_TOKEN": "synthetic-internal-token",
        "PASSWORD_TOKEN_SALT": "synthetic-password-salt",
        "REDIS_PASSWORD": "a" * 64,
        "COYOTE3_MONGO_URI": "mongodb://synthetic:synthetic@127.0.0.1:27017/?authSource=admin&replicaSet=synthetic",
        "COYOTE3_DB": "synthetic_application",
        "IDENTITY_DB": "synthetic_identity",
        "KNOWLEDGEBASE_DB": "synthetic_knowledgebase",
        "BAM_DB": "synthetic_bam",
        "PUBLIC_BASE_URL": "http://127.0.0.1:6801",
        "SCRIPT_NAME": "/synthetic",
        "COYOTE3_APP_NETWORK": "synthetic-app-network",
    }
    config = {
        "services": {
            "api": {
                "user": f"{os.getuid()}:{os.getgid()}",
                "environment": settings,
                "volumes": [
                    {"type": "bind", "source": str(path), "target": target}
                    for path, target in [
                        (roots["data"], "/data"),
                        (roots["logs"], "/app/logs"),
                        (center, "/app/center-config"),
                    ]
                ],
            },
            "proxy": {"ports": [{"target": 8088, "published": "6801"}]},
        },
        "networks": {"app": {"external": True, "name": "synthetic-app-network"}},
    }
    env_file = tmp_path / "synthetic.env"
    env_file.write_text("\n".join(f"{key}='{value}'" for key, value in settings.items()))
    rendered = tmp_path / "compose.json"
    log = tmp_path / "docker-calls.jsonl"
    docker = tmp_path / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['TEST_DOCKER_LOG'], 'a') as stream: stream.write(json.dumps(args) + '\\n')\n"
        "if 'config' in args: print(pathlib.Path(os.environ['TEST_COMPOSE_JSON']).read_text())\n"
        "elif 'inspect' in args: print('bridge')\n"
        "elif 'state' in args: print('fresh')\n"
    )
    docker.chmod(0o755)
    obsolete = tmp_path / "python3"
    obsolete.write_text("#!/bin/bash\necho obsolete-python-used >&2\nexit 55\n")
    obsolete.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "PYTHON_BIN": sys.executable,
        "TEST_COMPOSE_JSON": str(rendered),
        "TEST_DOCKER_LOG": str(log),
    }

    def run(script, *options):
        """Run a wrapper with its synthetic target and capture only synthetic output."""
        rendered.write_text(json.dumps(config))
        return subprocess.run(
            [
                "bash",
                str(ROOT / "scripts/deployment" / script),
                "--env-file",
                str(env_file),
                "--compose-file",
                str(ROOT / "deploy/compose/docker-compose.yml"),
                *options,
            ],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

    return config, center, log, run


def test_preflight_uses_resolved_mounts_and_the_supported_interpreter(deployment):
    """Host preflight must not parse container paths as host paths or use old python3."""
    _, _, _, run = deployment
    result = run("center_preflight.sh")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "preflight passed" in result.stdout
    assert "obsolete-python-used" not in result.stderr


def test_preflight_checks_optional_report_wording(deployment):
    """An invalid optional center file must fail before application deployment."""
    _, center, _, run = deployment
    (center / "report_presentation.toml").write_text('[empty_results]\nSNVV = "Unknown key"\n')
    result = run("center_preflight.sh")
    assert result.returncode != 0
    assert "SNVV" in result.stderr


@pytest.mark.parametrize("target", ["/data", "/app/logs"])
def test_preflight_rejects_read_only_application_storage(deployment, target):
    """Host permissions cannot make an explicitly read-only mount writable."""
    config, _, _, run = deployment
    for mount in config["services"]["api"]["volumes"]:
        if mount["target"] == target:
            mount["read_only"] = True
    result = run("center_preflight.sh")
    assert result.returncode != 0
    assert f"API requires {target} to be writable" in result.stderr


@pytest.mark.parametrize("origin", ["http://127.0.0.1:6801", "https://synthetic.invalid"])
def test_install_validation_accepts_an_origin_without_starting_services(deployment, origin):
    """The validation stage can run without triggering build, bootstrap or startup."""
    config, _, log, run = deployment
    config["services"]["api"]["environment"]["PUBLIC_BASE_URL"] = origin
    result = run("install_center.sh", "--project", "synthetic", "--steps", "validate")
    assert result.returncode == 0, result.stdout + result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert any("state" in call for call in calls)
    assert not any(
        "up" in call or "build" in call or "bootstrap_database.py" in call for call in calls
    )


def test_install_rejects_a_duplicated_public_prefix_before_container_operations(deployment):
    """Origin/path confusion produces a useful error before build or container execution."""
    config, _, log, run = deployment
    config["services"]["api"]["environment"]["PUBLIC_BASE_URL"] += "/synthetic"
    result = run("install_center.sh", "--project", "synthetic", "--steps", "validate")
    assert result.returncode != 0
    assert "Put the application prefix in SCRIPT_NAME only" in result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert not any("run" in call or "build" in call or "up" in call for call in calls)


@pytest.mark.parametrize("status", ["ok", "failed"])
def test_center_check_uses_zip_upload_and_requires_terminal_success(tmp_path, status):
    """A 200 response with a failed acknowledgement must not be reported as acceptance."""
    manifest = tmp_path / "synthetic.yaml"
    shutil.copyfile(ROOT / "tests/fixtures/ingest/generic_case_control.yaml", manifest)
    archive = tmp_path / "inputs.zip"
    with zipfile.ZipFile(archive, "w"):
        pass
    log = tmp_path / "curl-calls.jsonl"
    curl = tmp_path / "curl"
    curl.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['TEST_CURL_LOG'], 'a') as stream: stream.write(json.dumps(args) + '\\n')\n"
        "if '--form' in args:\n"
        " assert 'Authorization: Bearer synthetic-token' in sys.stdin.read()\n"
        " print(json.dumps({'status': os.environ['TEST_UPLOAD_STATUS'], 'message': 'Synthetic outcome', 'sample_id': 'synthetic-id'}))\n"
        " print('200', end='')\n"
    )
    curl.chmod(0o755)
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/deployment/center_check.sh"),
            "--api-base-url",
            "https://synthetic.invalid/coyote3",
            "--bearer-token",
            "synthetic-token",
            "--yaml-file",
            str(manifest),
            "--data-archive",
            str(archive),
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
            "PYTHON_BIN": sys.executable,
            "TEST_CURL_LOG": str(log),
            "TEST_UPLOAD_STATUS": status,
        },
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert (result.returncode == 0) == (status == "ok"), result.stdout + result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    upload = calls[-1]
    assert any(item.startswith("data_archive=@") for item in upload)
    assert "acknowledge=true" in upload
    assert not any("data_files" in item or "synthetic-token" in item for item in upload)
    assert manifest.is_file()
