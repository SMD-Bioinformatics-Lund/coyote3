"""Check host storage preparation without Docker or database access."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.deployment.prepare_host_directories import prepare


def configuration(tmp_path):
    """Return a resolved synthetic Compose service with local temporary mounts."""
    return {
        "services": {
            "api": {
                "user": f"{os.getuid()}:{os.getgid()}",
                "environment": {"ENV_NAME": "production"},
                "volumes": [
                    {"type": "bind", "source": str(tmp_path / name), "target": target}
                    for name, target in (("data", "/data"), ("logs", "/app/logs"))
                ]
                + [
                    {
                        "type": "bind",
                        "source": str(tmp_path / "inputs"),
                        "target": "/inputs",
                        "read_only": True,
                    }
                ],
            }
        }
    }


def test_preparation_creates_runtime_tree_and_preserves_existing_files(tmp_path):
    """Reruns preserve data and modes; unrelated input folders remain absent."""
    config = configuration(tmp_path)
    prepare(config)
    runtime = tmp_path / "data/coyote3_prod"
    assert (runtime / "reports").is_dir()
    assert (runtime / "ingest_staging").is_dir()
    assert (runtime / "copied_sample_files/yaml").is_dir()
    assert (tmp_path / "logs").is_dir()
    assert not (tmp_path / "inputs").exists()
    report = runtime / "reports/existing.txt"
    report.write_text("preserved")
    (runtime / "reports").chmod(0o700)
    prepare(config)
    assert report.read_text() == "preserved"
    assert (runtime / "reports").stat().st_mode & 0o777 == 0o700


def test_preparation_rejects_file_instead_of_directory(tmp_path):
    """Storage preparation never overwrites a file at a configured root."""
    (tmp_path / "data").write_text("preserved")
    with pytest.raises(NotADirectoryError):
        prepare(configuration(tmp_path))
    assert (tmp_path / "data").read_text() == "preserved"


def test_preparation_rejects_inaccessible_existing_storage_without_chmod(tmp_path):
    """An incompatible container identity fails without changing existing permissions."""
    config = configuration(tmp_path)
    prepare(config)
    data = tmp_path / "data"
    data.chmod(0o700)
    config["services"]["api"]["user"] = "123456:123456"
    with pytest.raises(PermissionError, match="Existing permissions were not changed"):
        prepare(config)
    assert data.stat().st_mode & 0o777 == 0o700


def test_wrapper_prepares_before_up_but_not_plain_config(tmp_path):
    """Deployment creates storage before Compose up; ordinary config stays read-only."""
    config = tmp_path / "render.json"
    config.write_text(json.dumps(configuration(tmp_path)))
    binary = tmp_path / "docker"
    binary.write_text(
        "#!/usr/bin/env python3\nimport sys,os,pathlib\n"
        "if sys.argv[-1] == 'version': sys.exit(0)\n"
        "if 'config' in sys.argv:\n"
        " print(pathlib.Path(os.environ['TEST_COMPOSE_JSON']).read_text())\n"
        "else:\n"
        " assert pathlib.Path(os.environ['TEST_STORAGE_ROOT'], 'data/coyote3_prod/reports').is_dir()\n"
    )
    binary.chmod(0o755)
    env = dict(
        os.environ,
        PATH=str(tmp_path) + os.pathsep + os.environ["PATH"],
        ENV_NAME="production",
        TEST_COMPOSE_JSON=str(config),
        TEST_STORAGE_ROOT=str(tmp_path),
    )
    root = Path(__file__).resolve().parents[2]
    command = ["bash", str(root / "scripts/deployment/compose-with-version.sh")]
    subprocess.run([*command, "config"], env=env, check=True, capture_output=True)
    assert not (tmp_path / "data").exists()
    subprocess.run([*command, "up", "-d"], env=env, check=True, capture_output=True)
    assert (tmp_path / "data/coyote3_prod/reports").is_dir()
