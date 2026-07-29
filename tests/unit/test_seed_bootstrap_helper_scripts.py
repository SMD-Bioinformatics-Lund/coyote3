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


def test_build_seed_bundle_canonicalizes_current_contract_shape(tmp_path):
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()

    (source_dir / "permissions.json").write_text(
        json.dumps([{"permission_name": "SAMPLES:VIEW"}]), encoding="utf-8"
    )
    (source_dir / "roles.json").write_text(
        json.dumps(
            [
                {
                    "role_id": "Admin",
                    "permissions": ["SAMPLES:VIEW", "samples:view"],
                    "deny_permissions": ["reports:delete"],
                }
            ]
        ),
        encoding="utf-8",
    )
    (source_dir / "users.json").write_text(
        json.dumps([{"username": "Seed.User@example.org"}]), encoding="utf-8"
    )
    (source_dir / "asp_configs.json").write_text(
        json.dumps(
            [
                {
                    "aspc_id": "assay_1_base_testing",
                    "asp_id": "assay_1",
                    "environment": "testing",
                    "subpanel_id": "base",
                    "asp_group": "Hematology",
                    "filters": {
                        "snvlists": ["seed_snv_list"],
                        "cnvlists": ["seed_cnv_list"],
                    },
                    "analysis_types": ["SNV", "CNV"],
                    "reporting": {"analysis": ["SNV", "CNV"], "report_sections": ["SNV"]},
                }
            ]
        ),
        encoding="utf-8",
    )
    (source_dir / "samples.json").write_text(
        json.dumps(
            [
                {
                    "name": "Seed Sample",
                    "asp_id": "Assay_1",
                    "subpanel_id": "base",
                    "environment": "testing",
                    "omics_layer": "dna",
                    "platform": "illumina",
                    "files": {"vcf_files": {"path": "/data/seed/sample.vcf"}},
                    "filters": {
                        "somatic": {
                            "snv": {"min_depth": 100, "snvlists": ["seed_snv_list"]},
                            "cnv": {"cnvlists": ["seed_cnv_list"]},
                            "coverage": {"warn_cov": 500},
                        },
                    },
                }
            ]
        ),
        encoding="utf-8",
    )

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

    permission = json.loads((dest_dir / "permissions.json").read_text())[0]
    assert permission == {
        "permission_id": "samples:view",
        "created_by": "admin@center.local",
        "updated_by": "admin@center.local",
        "created_on": "2026-03-30T00:00:00Z",
        "updated_on": "2026-03-30T00:00:00Z",
    }

    role = json.loads((dest_dir / "roles.json").read_text())[0]
    assert role["role_id"] == "admin"
    assert role["permissions"] == ["samples:view"]
    assert "deny_permissions" not in role

    user = json.loads((dest_dir / "users.json").read_text())[0]
    assert user["username"] == "seed.user"

    aspc = json.loads((dest_dir / "asp_configs.json").read_text())[0]
    assert aspc["aspc_id"] == "assay_1_base_testing"
    assert aspc["asp_id"] == "assay_1"
    assert aspc["subpanel_id"] == "base"
    assert aspc["environment"] == "testing"
    assert aspc["filters"]["snvlists"] == ["seed_snv_list"]
    assert aspc["filters"]["cnvlists"] == ["seed_cnv_list"]
    assert aspc["reporting"]["analysis"] == ["SNV", "CNV"]
    assert "assay_name" not in aspc
    assert "query" not in aspc

    sample = json.loads((dest_dir / "samples.json").read_text())[0]
    assert sample["subpanel_id"] == "base"
    assert sample["environment"] == "testing"
    assert sample["omics_layer"] == "dna"
    assert sample["platform"] == "illumina"
    assert sample["files"]["vcf_files"]["path"] == "/data/seed/sample.vcf"
    assert sample["filters"]["somatic"]["snv"]["snvlists"] == ["seed_snv_list"]
    assert sample["filters"]["somatic"]["cnv"]["cnvlists"] == ["seed_cnv_list"]
    assert sample["filters"]["somatic"]["coverage"]["warn_cov"] == 500
    assert "vcf_files" not in sample
    assert "comments" not in sample
    assert "reports" not in sample
    assert "groups" not in sample


def test_check_markdown_links_script_runs_clean():
    result = _run_script(["scripts/check_markdown_links.py"])
    assert result.returncode == 0, result.stderr
    assert "[ok] markdown internal links validated" in result.stdout
