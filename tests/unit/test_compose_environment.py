"""Exercise deployment environment selection without creating containers."""

import json
import os
import subprocess
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
            str(ROOT / "scripts/compose-with-version.sh"),
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
