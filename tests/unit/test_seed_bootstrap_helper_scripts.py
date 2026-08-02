"""Unit tests for seed/bootstrap helper scripts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import mongomock

from scripts.bootstrap_local_admin import (
    _deployment_is_initialized,
    _load_bootstrap_rbac,
    _superuser_exists,
)
from scripts.sync_rbac_catalog import synchronize_rbac_catalog

ROOT_DIR = Path(__file__).resolve().parents[2]


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_sync_rbac_catalog_preserves_custom_policy_and_adds_missing_grants():
    database = mongomock.MongoClient()["coyote3_test"]
    database.permissions.insert_one(
        {
            "permission_id": "assay.config:view",
            "label": "Center-custom label",
            "is_active": False,
        }
    )
    database.roles.insert_one(
        {
            "role_id": "manager",
            "permissions": ["assay.config:view", "center.custom:run"],
            "is_active": True,
        }
    )

    result = synchronize_rbac_catalog(
        database,
        permissions_collection="permissions",
        roles_collection="roles",
        permission_docs=[
            {
                "permission_id": "assay.config:view",
                "label": "Bundled label",
                "category": "Assay Configuration Management",
                "description": "View configuration",
                "tags": [],
                "is_active": True,
                "version": 1,
            },
            {
                "permission_id": "assay.config:edit",
                "label": "Edit assay configurations",
                "category": "Assay Configuration Management",
                "description": "Edit configuration",
                "tags": [],
                "is_active": True,
                "version": 1,
            },
        ],
        role_docs=[
            {
                "role_id": "manager",
                "permissions": ["assay.config:view", "assay.config:edit"],
            }
        ],
    )

    assert result == {
        "inserted_permissions": 1,
        "locked_permissions": 1,
        "inserted_roles": 0,
        "updated_roles": 1,
    }
    assert database.permissions.find_one({"permission_id": "assay.config:view"})["label"] == (
        "Center-custom label"
    )
    assert (
        database.permissions.find_one({"permission_id": "assay.config:view"})["system_managed"]
        is True
    )
    assert (
        database.permissions.find_one({"permission_id": "assay.config:view"})["is_active"] is True
    )
    assert (
        database.permissions.find_one({"permission_id": "assay.config:edit"})["system_managed"]
        is True
    )
    role = database.roles.find_one({"role_id": "manager"})
    assert set(role["permissions"]) == {
        "assay.config:view",
        "assay.config:edit",
        "center.custom:run",
    }

    repeated = synchronize_rbac_catalog(
        database,
        permissions_collection="permissions",
        roles_collection="roles",
        permission_docs=[
            {
                "permission_id": "assay.config:view",
                "label": "Bundled label",
                "category": "Assay Configuration Management",
                "description": "View configuration",
                "tags": [],
                "is_active": True,
                "version": 1,
            },
            {
                "permission_id": "assay.config:edit",
                "label": "Edit assay configurations",
                "category": "Assay Configuration Management",
                "description": "Edit configuration",
                "tags": [],
                "is_active": True,
                "version": 1,
            },
        ],
        role_docs=[
            {
                "role_id": "manager",
                "permissions": ["assay.config:view", "assay.config:edit"],
            }
        ],
    )
    assert repeated == {
        "inserted_permissions": 0,
        "locked_permissions": 0,
        "inserted_roles": 0,
        "updated_roles": 0,
    }


def test_sync_rbac_catalog_inserts_missing_bundled_role_without_removing_custom_roles():
    """Maintenance sync adds new application roles and preserves center roles."""
    client = mongomock.MongoClient()
    database = client.coyote3
    database.roles.insert_one(
        {
            "role_id": "center_reviewer",
            "name": "center_reviewer",
            "permissions": ["center.custom:run"],
            "is_active": True,
            "version": 1,
        }
    )

    result = synchronize_rbac_catalog(
        database,
        permissions_collection="permissions",
        roles_collection="roles",
        permission_docs=[
            {
                "permission_id": "app.controls:view",
                "label": "View application controls",
                "category": "Application Control Management",
                "description": "View runtime controls.",
                "tags": ["application", "controls", "view"],
                "is_active": True,
                "version": 1,
            }
        ],
        role_docs=[
            {
                "role_id": "operations_viewer",
                "name": "operations_viewer",
                "label": "Operations Viewer",
                "description": "Views operational state.",
                "color": "slate",
                "level": 180,
                "is_active": True,
                "permissions": ["app.controls:view"],
                "version": 1,
            }
        ],
    )

    assert result == {
        "inserted_permissions": 1,
        "locked_permissions": 0,
        "inserted_roles": 1,
        "updated_roles": 0,
    }
    assert database.roles.find_one({"role_id": "operations_viewer"})["permissions"] == [
        "app.controls:view"
    ]
    assert database.roles.find_one({"role_id": "center_reviewer"})["permissions"] == [
        "center.custom:run"
    ]


def test_application_bootstrap_catalog_contains_canonical_permissions_and_roles():
    """The repository ships the complete first-deployment governance catalog."""
    permission_docs, role_docs = _load_bootstrap_rbac(
        ROOT_DIR / "api" / "config" / "bootstrap" / "rbac"
    )
    permission_ids = {str(doc["permission_id"]) for doc in permission_docs}
    roles = {str(doc["role_id"]): doc for doc in role_docs}

    assert "notification.broadcast:create" in permission_ids
    assert all(doc.get("system_managed") is True for doc in permission_docs)
    assert {"user:list", "user:view", "user:create", "user:edit", "user:delete"} <= (permission_ids)
    assert {"user:manage", "user:role:edit", "user:group:edit"} <= permission_ids
    assert {
        "superuser",
        "asp_manager",
        "aspc_manager",
        "isgl_manager",
        "operations_viewer",
        "app_control_operator",
        "user_account_manager",
    } <= set(roles)
    assert set(roles["superuser"]["permissions"]) == permission_ids
    assert set(roles["user_account_manager"]["permissions"]) == {
        "user:list",
        "user:view",
        "user:create",
        "user:edit",
        "user:delete",
        "role:list",
        "role:view",
        "permission.policy:list",
        "permission.policy:view",
    }


def test_first_deployment_bootstrap_detects_empty_partial_and_complete_state():
    """First-run bootstrap runs only against empty governance collections."""
    database = mongomock.MongoClient()["coyote3_test"]
    assert _deployment_is_initialized(database) is False
    assert _superuser_exists(database) is False

    database.permissions.insert_one({"permission_id": "sample:view"})
    assert _deployment_is_initialized(database) is True
    assert _superuser_exists(database) is False

    database.users.insert_one({"username": "root", "roles": ["superuser"]})
    assert _superuser_exists(database) is True


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
                    "reporting": {"report_sections": ["SNV"]},
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
        "system_managed": True,
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
    assert aspc["analysis_types"] == ["SNV", "CNV"]
    assert aspc["reporting"]["report_sections"] == ["SNV"]
    assert "analysis" not in aspc["reporting"]
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
