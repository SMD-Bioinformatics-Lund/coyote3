"""Unit tests for seed/bootstrap helper scripts."""

from __future__ import annotations

import json
import subprocess
import sys


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_seed_payload_utils_count_and_payload(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "roles.json").write_text(
        json.dumps([{"role_id": "admin"}, {"role_id": "viewer"}]), encoding="utf-8"
    )

    count_result = _run_script(
        [
            "scripts/seed_payload_utils.py",
            "count",
            "--seed-dir",
            str(seed_dir),
            "--collection",
            "roles",
        ]
    )
    assert count_result.returncode == 0, count_result.stderr
    assert count_result.stdout.strip() == "2"

    payload_result = _run_script(
        [
            "scripts/seed_payload_utils.py",
            "payload",
            "--seed-dir",
            str(seed_dir),
            "--collection",
            "roles",
            "--ignore-duplicates",
        ]
    )
    assert payload_result.returncode == 0, payload_result.stderr
    payload = json.loads(payload_result.stdout)
    assert payload["collection"] == "roles"
    assert payload["ignore_duplicates"] is True
    assert len(payload["documents"]) == 2


def test_build_seed_bundle_normalizes_and_stamps(tmp_path):
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()

    seed_docs = [
        {
            "permission_id": "REPORT:VIEW",
            "created_on": {"$date": "2024-01-01T00:00:00Z"},
            "owner_id": {"$oid": "507f1f77bcf86cd799439011"},
        }
    ]
    (source_dir / "permissions.json").write_text(json.dumps(seed_docs), encoding="utf-8")

    result = _run_script(
        [
            "scripts/build_seed_bundle.py",
            "--seed-source",
            str(source_dir),
            "--dest-dir",
            str(dest_dir),
            "--seed-actor",
            "admin@center.local",
            "--seed-time",
            "2026-03-30T00:00:00Z",
        ]
    )
    assert result.returncode == 0, result.stderr
    assert "[ok] normalized seed bundle:" in result.stdout

    output_docs = json.loads((dest_dir / "permissions.json").read_text(encoding="utf-8"))
    assert output_docs[0]["permission_id"] == "report:view"
    assert output_docs[0]["created_on"] == "2026-03-30T00:00:00Z"
    assert output_docs[0]["owner_id"] == "507f1f77bcf86cd799439011"
    assert output_docs[0]["created_by"] == "admin@center.local"
    assert output_docs[0]["updated_by"] == "admin@center.local"


def test_check_markdown_links_script_runs_clean():
    result = _run_script(["scripts/check_markdown_links.py"])
    assert result.returncode == 0, result.stderr
    assert "[ok] markdown internal links validated" in result.stdout
