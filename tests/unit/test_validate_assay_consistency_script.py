"""Tests for center seed dependency/assay validation script."""

from __future__ import annotations

import gzip
import json
import subprocess
import sys
from pathlib import Path


def _run_validator(
    seed_path: Path, *, reference_dirs: tuple[Path, ...] = ()
) -> subprocess.CompletedProcess[str]:
    python_bin = sys.executable or "python3"
    command = [
        python_bin,
        "scripts/validate_assay_consistency.py",
        "--seed-file",
        str(seed_path),
    ]
    for reference_dir in reference_dirs:
        command.extend(("--reference-seed-data", str(reference_dir)))
    return subprocess.run(
        command,
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )


def _populate_seed_dir(seed_path: Path) -> None:
    seed_src = Path("demo_data/collections/all_collections_dummy")
    for file in seed_src.glob("*.json"):
        (seed_path / file.name).write_text(file.read_text(encoding="utf-8"), encoding="utf-8")

    reference_map = {
        Path("api/config/bootstrap/reference/hgnc_genes.seed.ndjson"): "hgnc_genes.json",
        Path("api/config/bootstrap/rbac/permissions.seed.ndjson"): "permissions.json",
        Path("api/config/bootstrap/rbac/roles.seed.ndjson"): "roles.json",
        Path("api/config/bootstrap/reference/vep_metadata.seed.ndjson"): "vep_metadata.json",
    }
    for source, target_name in reference_map.items():
        if not source.exists() and source.suffix != ".gz":
            source = Path(f"{source}.gz")
        if not source.exists():
            continue
        docs = []
        opener = gzip.open if source.suffix == ".gz" else open
        with opener(source, "rt", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if text:
                    docs.append(json.loads(text))
        (seed_path / target_name).write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")


def test_validate_assay_consistency_accepts_all_collections_seed_dir(tmp_path):
    seed_path = tmp_path / "seed"
    seed_path.mkdir()
    _populate_seed_dir(seed_path)
    result = _run_validator(seed_path)
    assert result.returncode == 0, result.stderr
    assert "[ok] assay consistency checks passed" in result.stdout


def test_validate_assay_consistency_merges_separate_rbac_and_reference_packs(tmp_path):
    seed_path = tmp_path / "seed"
    seed_path.mkdir()
    for source_name in ("asp_configs.json", "assay_specific_panels.json"):
        source = Path("api/config/bootstrap/demo_center") / source_name
        (seed_path / source_name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    result = _run_validator(
        seed_path,
        reference_dirs=(
            Path("api/config/bootstrap/rbac"),
            Path("api/config/bootstrap/reference"),
        ),
    )

    assert result.returncode == 0, result.stderr
    assert "[ok] assay consistency checks passed" in result.stdout


def test_validate_assay_consistency_rejects_missing_role_reference(tmp_path):
    seed_path = tmp_path / "seed_bad"
    seed_path.mkdir()
    _populate_seed_dir(seed_path)
    (seed_path / "roles.json").write_text("[]\n", encoding="utf-8")

    result = _run_validator(seed_path)
    assert result.returncode != 0
    combined = (result.stdout + "\n" + result.stderr).lower()
    assert "bootstrap dependency errors" in combined
    assert "required collection 'roles'" in combined


def test_validate_assay_consistency_rejects_extended_json_datetime_wrappers(tmp_path):
    seed_path = tmp_path / "seed_bad_extjson"
    seed_path.mkdir()
    _populate_seed_dir(seed_path)

    permissions = seed_path / "permissions.json"
    payload = json.loads(permissions.read_text(encoding="utf-8"))
    payload[0]["created_on"] = {"$date": "2025-05-20T14:07:46.583Z"}
    permissions.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_validator(seed_path)
    assert result.returncode != 0
    combined = (result.stdout + "\n" + result.stderr).lower()
    assert "seed contract-shape errors" in combined
    assert "extended json wrappers" in combined
