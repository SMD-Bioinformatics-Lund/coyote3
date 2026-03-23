"""Tests for center seed dependency/assay validation script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_validator(seed_path: Path) -> subprocess.CompletedProcess[str]:
    python_bin = sys.executable or "python3"
    return subprocess.run(
        [
            python_bin,
            "scripts/validate_assay_consistency.py",
            "--seed-file",
            str(seed_path),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )


def test_validate_assay_consistency_accepts_all_collections_seed_dir(tmp_path):
    seed_src = Path("tests/fixtures/db_dummy/all_collections_dummy")
    seed_path = tmp_path / "seed"
    seed_path.mkdir()
    for file in seed_src.glob("*.json"):
        (seed_path / file.name).write_text(file.read_text(encoding="utf-8"), encoding="utf-8")
    result = _run_validator(seed_path)
    assert result.returncode == 0, result.stderr
    assert "[ok] assay consistency checks passed" in result.stdout


def test_validate_assay_consistency_rejects_missing_role_reference(tmp_path):
    seed_src = Path("tests/fixtures/db_dummy/all_collections_dummy")
    seed_path = tmp_path / "seed_bad"
    seed_path.mkdir()
    for file in seed_src.glob("*.json"):
        target = seed_path / file.name
        if file.name == "roles.json":
            target.write_text("[]\n", encoding="utf-8")
        else:
            target.write_text(file.read_text(encoding="utf-8"), encoding="utf-8")

    result = _run_validator(seed_path)
    assert result.returncode != 0
    combined = (result.stdout + "\n" + result.stderr).lower()
    assert "bootstrap dependency errors" in combined
    assert "required collection 'roles'" in combined


def test_validate_assay_consistency_rejects_extended_json_datetime_wrappers(tmp_path):
    seed_src = Path("tests/fixtures/db_dummy/all_collections_dummy")
    seed_path = tmp_path / "seed_bad_extjson"
    seed_path.mkdir()
    for file in seed_src.glob("*.json"):
        target = seed_path / file.name
        target.write_text(file.read_text(encoding="utf-8"), encoding="utf-8")

    permissions = seed_path / "permissions.json"
    payload = json.loads(permissions.read_text(encoding="utf-8"))
    payload[0]["created_on"] = {"$date": "2025-05-20T14:07:46.583Z"}
    permissions.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_validator(seed_path)
    assert result.returncode != 0
    combined = (result.stdout + "\n" + result.stderr).lower()
    assert "seed contract-shape errors" in combined
    assert "extended json wrappers" in combined
