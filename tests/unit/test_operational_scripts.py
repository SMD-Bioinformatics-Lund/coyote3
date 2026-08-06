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
    assert "--mongo-uri, --db, and --out-dir are required" in missing_result.stdout


def test_restore_script_requires_explicit_patient_data_confirmation(tmp_path: Path) -> None:
    archive = tmp_path / "backup.archive.gz"
    archive.write_bytes(b"not a real archive")

    result = _run_script(
        "mongo_restore_archive.sh",
        "--mongo-uri",
        "mongodb://example.invalid:27017",
        "--db",
        "coyote3_test",
        "--archive",
        str(archive),
    )

    assert result.returncode == 3
    assert "restore blocked" in result.stdout
    assert "starting restore" not in result.stdout
