"""Exercise deployment environment selection without creating containers."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


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
        "#!/usr/bin/env python3\nimport os,sys\n"
        "if 'config' in sys.argv:\n"
        " assert os.environ.get('COYOTE3_IMAGE_TAG'), 'Missing image tag'\n"
        " assert os.environ.get('LOG_LEVEL') == 'INFO'\n"
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
