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


def test_validate_assay_consistency_accepts_center_template_seed(tmp_path):
    seed_src = Path("tests/fixtures/db_dummy/center_template_seed.json")
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(seed_src.read_text(encoding="utf-8"), encoding="utf-8")
    result = _run_validator(seed_path)
    assert result.returncode == 0, result.stderr
    assert "[ok] assay consistency checks passed" in result.stdout


def test_validate_assay_consistency_rejects_missing_role_reference(tmp_path):
    seed_src = Path("tests/fixtures/db_dummy/center_template_seed.json")
    payload = json.loads(seed_src.read_text(encoding="utf-8"))
    payload["roles"] = []
    seed_path = tmp_path / "seed_bad.json"
    seed_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_validator(seed_path)
    assert result.returncode != 0
    combined = (result.stdout + "\n" + result.stderr).lower()
    assert "bootstrap dependency errors" in combined
    assert "required collection 'roles'" in combined
