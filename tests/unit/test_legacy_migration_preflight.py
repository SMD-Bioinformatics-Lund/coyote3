"""Migration gates use installed configuration and report missing evidence without guessing."""

from copy import deepcopy
from pathlib import Path

import mongomock
import pytest
from bson import ObjectId

from scripts.migration_common.apply_bundle import apply_plan
from scripts.migration_common.commands import run
from scripts.migration_common.conversion import d4_coverage_plan, independent_plan, prepare_finding
from scripts.migration_common.offline import digest, private_json, read_json
from scripts.migration_common.schema_inventory import inventory_export
from scripts.migration_common.target_catalog import (
    CATALOG_COLLECTIONS,
    bind_sample_review,
    validate_snapshot,
)
from tests.unit.test_offline_legacy_migrations import make_index, sample


def catalog():
    """Use current synthetic contract fixtures as preinstalled target configuration."""
    root = Path("demo_data/collections/all_collections_dummy")
    records = {name: read_json(root / f"{name}.json")[:1] for name in CATALOG_COLLECTIONS}
    for rows in records.values():
        for row in rows:
            row["_id"] = ObjectId()
    records["assay_groups"][0]["group_id"] = "hematology"
    result = {"format": 1, "collections": records, "sha256": digest(records)}
    validate_snapshot(result)
    return result


def test_binding_uses_explicit_revision_and_does_not_invent_historical_metadata():
    target = catalog()
    aspc = target["collections"]["asp_configs"][0]
    result = bind_sample_review(
        target, {}, {"sample": {"metadata": {"current_aspc_id": aspc["_id"]}}}
    )
    fields = result["sample"]["metadata"]
    assert fields["asp_id"] == aspc["asp_id"]
    assert fields["current_aspc_version"] == aspc["version"]
    assert (
        not {"case_id", "pipeline", "sequencing_scope", "time_added", "ingested_by"} & fields.keys()
    )
    with pytest.raises(ValueError, match="Select one"):
        bind_sample_review(target, {}, {})
    with pytest.raises(ValueError, match="conflicts"):
        bind_sample_review(
            target,
            {},
            {
                "sample": {
                    "metadata": {
                        "current_aspc_id": aspc["_id"],
                        "asp_id": "other",
                    }
                }
            },
        )


@pytest.mark.parametrize("missing", ["assay_groups", "assay_specific_panels", "asp_configs"])
def test_missing_target_prerequisites_stop_preflight(missing):
    target = catalog()
    target["collections"][missing] = []
    target["sha256"] = digest(target["collections"])
    with pytest.raises(ValueError, match="Install"):
        validate_snapshot(target)


def test_target_gene_list_and_subpanel_relationships_are_required():
    target = catalog()
    aspc = target["collections"]["asp_configs"][0]
    aspc["filters"]["somatic"]["snv"]["snvlists"] = ["not-installed"]
    target["sha256"] = digest(target["collections"])
    with pytest.raises(ValueError, match="ISGL"):
        validate_snapshot(target)
    aspc["filters"]["somatic"]["snv"]["snvlists"] = []
    aspc["subpanel_id"] = "missing-scope"
    target["sha256"] = digest(target["collections"])
    with pytest.raises(ValueError, match="subpanel"):
        validate_snapshot(target)


def test_target_change_blocks_apply_before_any_insert():
    target = catalog()
    db = mongomock.MongoClient().test
    for name, rows in target["collections"].items():
        db[name].insert_many(deepcopy(rows))
    plan = {"blacklist": [{"_id": ObjectId(), "assay_group": "hematology", "pos": "1_1"}]}
    with pytest.raises(ValueError, match="changed since conversion"):
        apply_plan(db, plan, expected_catalog_digest="stale")
    assert db.blacklist.count_documents({}) == 0


def test_coverage_measurements_are_never_converted_to_blacklist_entries(tmp_path):
    original = sample()
    measurement = {
        "_id": ObjectId(),
        "SAMPLE_ID": str(original["_id"]),
        "sample": original["name"],
        "genes": {},
    }
    source = make_index(tmp_path, 3, {"samples": [original], "group_coverage": [measurement]})
    try:
        assert d4_coverage_plan(source, str(original["_id"]), {}) == [measurement]
        assert independent_plan(source, "d4_coverage_blacklist", {}) == {
            "d4_coverage_blacklist": []
        }
    finally:
        source.close()


def test_ambiguous_coverage_requires_complete_digest_bound_selection(tmp_path):
    original = sample()
    a = {
        "_id": ObjectId(),
        "SAMPLE_ID": str(original["_id"]),
        "sample": original["name"],
        "genes": {},
    }
    b = {**a, "_id": ObjectId()}
    source = make_index(
        tmp_path, 3, {"samples": [original], "panel_cov": [a], "group_coverage": [b]}
    )
    try:
        with pytest.raises(ValueError, match="Multiple D4"):
            d4_coverage_plan(source, str(original["_id"]), {})
        decision = {
            "source_sha256": digest(
                [
                    {"collection": "panel_cov", "document": a},
                    {"collection": "group_coverage", "document": b},
                ]
            ),
            "collection": "panel_cov",
            "record_id": str(a["_id"]),
            "reason": "Reviewed synthetic duplicate",
            "archive_unselected": True,
        }
        assert d4_coverage_plan(source, str(original["_id"]), decision) == [a]
    finally:
        source.close()


@pytest.mark.parametrize("missing_pipeline", [False, True])
def test_conversion_writes_success_or_blocked_run_report(tmp_path, monkeypatch, missing_pipeline):
    target = catalog()
    original = sample()
    original["profile"] = "production"
    if missing_pipeline:
        original.pop("pipeline")
    source = make_index(tmp_path, 2, {"samples": [original]})
    source.close()
    audit = inventory_export(tmp_path / "export", tmp_path / "audit", 2)
    review = {
        "schema_audit": {
            "manifest_sha256": digest(audit),
            "reviewed_by": "fixture.operator",
            "reviewed_on": "2026-01-01",
        },
        "samples": {
            str(original["_id"]): {
                "sample": {
                    "metadata": {
                        "current_aspc_id": target["collections"]["asp_configs"][0]["_id"],
                        "sequencing_scope": "panel",
                        "ingest_status": "ready",
                    }
                }
            }
        },
    }
    private_json(tmp_path / "target.json", target)
    private_json(tmp_path / "review.json", review)
    monkeypatch.setattr(
        "sys.argv",
        [
            "migrate_sample.py",
            "--index",
            str(tmp_path / "source.sqlite"),
            "--schema-audit",
            str(tmp_path / "audit"),
            "--target-catalog",
            str(tmp_path / "target.json"),
            "--review",
            str(tmp_path / "review.json"),
            "--sample-id",
            str(original["_id"]),
            "--output",
            str(tmp_path / "bundle"),
        ],
    )
    assert run(2, "sample") == int(missing_pipeline)
    report = read_json(tmp_path / "bundle.migration.json")
    assert report["status"] == ("blocked" if missing_pipeline else "complete")
    assert (tmp_path / "bundle.migration.md").exists()
    assert (tmp_path / "bundle.migration.json").stat().st_mode & 0o777 == 0o600
    if missing_pipeline:
        assert not (tmp_path / "bundle").exists()
        assert any(item["field"] == ["pipeline"] for item in report["fields"])


def test_scalar_biomarker_without_units_is_not_fabricated():
    with pytest.raises(ValueError, match="explicit typed measurement"):
        prepare_finding("biomarkers", {"_id": ObjectId(), "biomarker": "TMB", "value": 2})
