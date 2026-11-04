"""Exercise deployment environment selection without creating containers."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "definitions,legacy",
    [
        (["deploy/legacy/docker-compose.yml"], True),
        (["deploy/legacy/docker-compose.yml", "deploy/legacy/docker-compose.stage.yml"], True),
        (["deploy/legacy/docker-compose.yml", "deploy/legacy/docker-compose.test.yml"], True),
        (["deploy/legacy/docker-compose.dev.yml"], True),
        (["deploy/compose/docker-compose.yml"], False),
        (["deploy/compose/docker-compose.yml", "deploy/compose/docker-compose.dev.yml"], False),
    ],
)
def test_old_host_build_compatibility_is_confined_to_legacy_compose(definitions, legacy):
    """Merged build selections keep Bullseye archives away from modern deployments."""
    if not shutil.which("docker"):
        pytest.skip("Docker Compose CLI required; no Docker daemon is used")
    command = ["docker", "compose", "--profile", "*", "--env-file", "deploy/env/example.env"]
    for definition in definitions:
        command.extend(["-f", definition])
    result = subprocess.run(
        [*command, "config", "--format", "json"],
        cwd=ROOT,
        env={**os.environ, "COYOTE3_IMAGE_TAG": "synthetic-compatibility-test"},
        capture_output=True,
        text=True,
        check=True,
    )
    builds = {
        name: service["build"]
        for name, service in json.loads(result.stdout)["services"].items()
        if service.get("build") and name != "frontend"
    }
    assert "api" in builds and "docs" in builds
    for name, build in builds.items():
        dockerfile = build["dockerfile"]
        if legacy:
            assert dockerfile == (
                "docker/Dockerfile.docs.legacy" if name == "docs" else "docker/Dockerfile.legacy"
            )
            assert build["args"]["PYTHON_BASE_IMAGE"] == "python:3.12-slim-bullseye"
            assert build["network"] == "host"
        else:
            assert ".legacy" not in dockerfile
            source = (ROOT / dockerfile).read_text()
            assert "slim-bookworm" in source.splitlines()[0]
            assert "archive.debian.org" not in source


@pytest.mark.parametrize(
    "label,suffix,level",
    [
        ("development", "dev", "DEBUG"),
        ("test", "test", "DEBUG"),
        ("staging", "stage", "DEBUG"),
        ("production", "prod", "INFO"),
        ("prod", "prod", "INFO"),
    ],
)
@pytest.mark.parametrize("explicit", [False, True])
def test_wrapper_selects_environment(tmp_path, label, suffix, level, explicit):
    """The wrapper derives defaults and never overwrites explicit logging settings."""
    binary = tmp_path / "docker"
    binary.write_text(
        "#!/usr/bin/env python3\nimport os,json,sys\n"
        "if sys.argv[-1] != 'version':\n"
        " print(json.dumps({k:os.environ.get(k) for k in "
        "['COYOTE3_IMAGE_TAG','CELERY_LOG_LEVEL','LOG_LEVEL']}))\n"
    )
    binary.chmod(0o755)
    env_file = tmp_path / "settings.env"
    env_file.write_text(
        f"ENV_NAME='{label}' # deployment\n"
        + ("LOG_LEVEL='INFO'\nCELERY_LOG_LEVEL='WARNING'\n" if explicit else "")
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"ENV_NAME", "LOG_LEVEL", "CELERY_LOG_LEVEL"}
    }
    env["PATH"] = str(tmp_path) + os.pathsep + env["PATH"]
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/deployment/compose-with-version.sh"),
            "--env-file",
            str(env_file),
            "config",
        ],
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    settings = json.loads(result.stdout.splitlines()[-1])
    from api.version import __version__

    assert settings["COYOTE3_IMAGE_TAG"] == (
        __version__ if suffix == "prod" else f"{__version__}-{suffix}"
    )
    assert settings["LOG_LEVEL"] == ("INFO" if explicit else level)
    assert settings["CELERY_LOG_LEVEL"] == ("WARNING" if explicit else level)


def test_center_preflight_resolves_image_tag_without_exported_version(tmp_path):
    """A fresh operator shell can validate production Compose through the wrapper."""
    binary = tmp_path / "docker"
    binary.write_text(
        "#!/usr/bin/env python3\nimport os,sys,json,shlex\n"
        "if 'config' in sys.argv:\n"
        " assert os.environ.get('COYOTE3_IMAGE_TAG'), 'Missing image tag'\n"
        " assert os.environ.get('LOG_LEVEL') == 'INFO'\n"
        " source=sys.argv[sys.argv.index('--env-file')+1]\n"
        " settings=dict(shlex.split(line)[0].split('=',1) for line in open(source) if line.strip())\n"
        " api={'environment':settings,'user':settings['COYOTE3_UID']+':'+settings['COYOTE3_GID']}\n"
        f" center={str(ROOT / 'config/examples/center')!r}\n"
        " api['volumes']=[{'type':'bind','target':target,'source':path} for target,path in "
        "[('/app/center-config',center),('/data',settings['COYOTE3_DATA_HOST_ROOT']),"
        "('/app/logs',settings['COYOTE3_LOGS_HOST_ROOT'])]]\n"
        " print(json.dumps({'services':{'api':api}}))\n"
    )
    binary.chmod(0o755)
    values = {
        "ENV_NAME": "production",
        "SECRET_KEY": "synthetic-preflight-secret",
        "INTERNAL_API_TOKEN": "synthetic-preflight-token",
        "PASSWORD_TOKEN_SALT": "synthetic-preflight-salt",
        "REDIS_PASSWORD": "a" * 64,
        "COYOTE3_MONGO_URI": "mongodb://127.0.0.1:27017/",
        "COYOTE3_DB": "preflight_app",
        "IDENTITY_DB": "preflight_identity",
        "KNOWLEDGEBASE_DB": "preflight_kb",
        "BAM_DB": "preflight_bam",
        "COYOTE3_APP_NETWORK": "preflight-net",
        "COYOTE3_UID": str(os.getuid()),
        "COYOTE3_GID": str(os.getgid()),
        "COYOTE3_DATA_HOST_ROOT": str(tmp_path),
        "COYOTE3_LOGS_HOST_ROOT": str(tmp_path),
    }
    env_file = tmp_path / "settings.env"
    env_file.write_text("".join(f"{key}='{value}'\n" for key, value in values.items()))
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"ENV_NAME", "LOG_LEVEL", "CELERY_LOG_LEVEL", "COYOTE3_IMAGE_TAG"}
    }
    env.update(PATH=str(tmp_path) + os.pathsep + env["PATH"], PYTHON_BIN=sys.executable)
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/deployment/center_preflight.sh"),
            "--env-file",
            str(env_file),
            "--compose-file",
            "deploy/compose/docker-compose.yml",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[ok] preflight passed" in result.stdout
