from __future__ import annotations

import gzip
import os
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("selection", ["repository", "active", "explicit"])
def test_family_coverage_uses_project_root_and_selected_interpreter(tmp_path, selection):
    """Running from outside the repo preserves interpreter precedence and coverage location."""
    root = tmp_path / "project"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    script = scripts / "run_family_coverage_gates.sh"
    script.write_text(
        (REPOSITORY_ROOT / "scripts/run_family_coverage_gates.sh").read_text(), encoding="utf-8"
    )
    (root / ".coverage").touch()
    interpreters = {}
    for name in ("repository", "active", "explicit"):
        path = root / (".venv" if name == "repository" else name) / "bin/python"
        path.parent.mkdir(parents=True)
        path.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name}:$PWD:$*"\n', encoding="utf-8")
        path.chmod(0o700)
        interpreters[name] = path
    env = {
        key: value for key, value in os.environ.items() if key not in {"PYTHON_BIN", "VIRTUAL_ENV"}
    }
    if selection in {"active", "explicit"}:
        env["VIRTUAL_ENV"] = str(interpreters["active"].parents[1])
    if selection == "explicit":
        env["PYTHON_BIN"] = str(interpreters["explicit"])
    result = subprocess.run(
        ["bash", str(script), "--from-existing"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.count(f"{selection}:{root}:-m coverage report") == 5


def _run_script(script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(REPOSITORY_ROOT / "scripts" / script), *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_backup_script_documents_and_enforces_required_arguments() -> None:
    help_result = _run_script("mongo_backup_archive.sh", "--help")
    assert help_result.returncode == 0
    assert "Create a compressed MongoDB backup archive" in help_result.stdout

    missing_result = _run_script("mongo_backup_archive.sh")
    assert missing_result.returncode == 2
    assert "--mongo-uri and --out-dir are required" in missing_result.stdout


def test_restore_script_requires_explicit_patient_data_confirmation(tmp_path: Path) -> None:
    archive = tmp_path / "backup.archive.gz"
    archive.write_bytes(b"not a real archive")

    result = _run_script(
        "mongo_restore_archive.sh",
        "--mongo-uri",
        "mongodb://example.invalid:27017",
        "--archive",
        str(archive),
    )

    assert result.returncode == 3
    assert "restore blocked" in result.stdout
    assert "starting restore" not in result.stdout


def test_public_proxy_applies_browser_security_headers() -> None:
    script = (REPOSITORY_ROOT / "deploy/compose/nginx/render-config.sh").read_text(encoding="utf-8")

    assert 'add_header X-Content-Type-Options "nosniff" always;' in script
    assert 'add_header X-Frame-Options "DENY" always;' in script
    assert "add_header Content-Security-Policy" in script
    assert "Strict-Transport-Security" in script
    assert r"proxy_set_header X-Forwarded-Proto \$forwarded_proto;" in script


def test_restore_does_not_print_database_credentials(tmp_path: Path, monkeypatch) -> None:
    """Exercise restore logging without contacting Docker or a database."""
    archive = tmp_path / "synthetic.archive.gz"
    archive.write_bytes(gzip.compress(b"synthetic archive"))
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    docker.chmod(0o700)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    uri = "mongodb://restore-user:synthetic-password@example.invalid:27017/admin"
    result = _run_script(
        "mongo_restore_archive.sh",
        "--mongo-uri",
        uri,
        "--archive",
        str(archive),
        "--confirm",
        "RESTORE_PATIENT_DATA",
    )
    assert result.returncode == 0, result.stderr
    assert "restore complete" in result.stdout
    assert uri not in result.stdout + result.stderr
    assert "synthetic-password" not in result.stdout + result.stderr


def test_preflight_checks_runtime_mount_write_access() -> None:
    script = (REPOSITORY_ROOT / "scripts/center_preflight.sh").read_text(encoding="utf-8")

    assert 'data.get("COYOTE3_UID", "10001")' in script
    assert 'data.get("COYOTE3_GID", "10001")' in script
    assert '("COYOTE3_DATA_HOST_ROOT", "COYOTE3_LOGS_HOST_ROOT")' in script
    assert "has_access(value, write=True)" in script


def test_preflight_requires_explicit_database_names() -> None:
    script = (REPOSITORY_ROOT / "scripts/center_preflight.sh").read_text(encoding="utf-8")

    assert "for key in COYOTE3_DB IDENTITY_DB KNOWLEDGEBASE_DB BAM_DB" in script
    assert "PASSWORD_TOKEN_SALT COYOTE3_APP_NETWORK" in script
    assert "from api.config.mongo import mongo_endpoints" in script
    assert "mongo_endpoints(data)" in script
    assert "auth_source != db" not in script


def test_center_check_forwards_an_explicit_authentication_provider() -> None:
    script = (REPOSITORY_ROOT / "scripts/center_check.sh").read_text(encoding="utf-8")

    assert 'PROVIDER="local"' in script
    assert '--provider) PROVIDER="$2"; shift 2 ;;' in script
    assert '--provider "$PROVIDER"' in script

    invalid_result = _run_script("center_check.sh", "--provider", "unsupported")
    assert invalid_result.returncode == 2
    assert "--provider must be local or ldap" in invalid_result.stderr


def test_api_images_include_center_check_runtime_dependencies() -> None:
    for relative_path in ("docker/Dockerfile", "docker/Dockerfile.dev"):
        dockerfile = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        install_block = dockerfile.split("apt-get install -y --no-install-recommends", 1)[1]
        install_block = install_block.split("&&", 1)[0]
        assert "curl" in install_block.split()
