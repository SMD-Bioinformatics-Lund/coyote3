from __future__ import annotations

import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


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


def test_preflight_checks_runtime_mount_write_access() -> None:
    script = (REPOSITORY_ROOT / "scripts/center_preflight.sh").read_text(encoding="utf-8")

    assert 'data.get("COYOTE3_UID", "10001")' in script
    assert 'data.get("COYOTE3_GID", "10001")' in script
    assert '("COYOTE3_DATA_HOST_ROOT", "COYOTE3_LOGS_HOST_ROOT")' in script
    assert "has_access(value, write=True)" in script


def test_preflight_requires_explicit_database_names() -> None:
    script = (REPOSITORY_ROOT / "scripts/center_preflight.sh").read_text(encoding="utf-8")

    assert "for key in MONGO_URI COYOTE3_DB BAM_DB SECRET_KEY" in script
    assert 'data.get("COYOTE3_DB", "")' in script
    assert "ERROR: BAM_DB must be set" in script
