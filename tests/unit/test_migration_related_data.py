"""Related-data stages preserve ownership and isolate independently selected collections."""

from pathlib import Path

import pytest
from bson import ObjectId

from scripts.migration_common.conversion import sample_plan, selected_collections
from scripts.migration_common.offline import read_json
from tests.unit.test_offline_legacy_migrations import make_index, review, sample


@pytest.mark.parametrize("version", [2, 3])
@pytest.mark.parametrize(
    "collection",
    ["cnvs", "translocations", "biomarkers", "rna_expression", "rna_qc", "rna_classification"],
)
def test_related_collection_can_be_converted_independently(tmp_path, version, collection):
    """Each selected type migrates while malformed unrelated variants/QC are left for review."""
    owner = sample()
    owner["QC"] = [{"unreviewed": True}, {"unreviewed": True}]
    payload = read_json(
        Path(f"tests/fixtures/collections/all_collections_dummy/{collection}.json")
    )[0]
    payload.update(_id=ObjectId(), SAMPLE_ID=str(owner["_id"]))
    physical = {
        "cnvs": "cnvs" if version == 3 else "cnvs_wgs",
        "translocations": "transloc",
        "biomarkers": "biomarkers",
    }
    records = {
        "samples": [owner],
        "variants" if version == 3 else "variants_idref": [
            {"_id": ObjectId(), "SAMPLE_ID": str(owner["_id"])}
        ],
    }
    if collection in physical:
        records[physical[collection]] = [payload]
    else:
        field = {"rna_expression": "expr", "rna_qc": "QC", "rna_classification": "classification"}[
            collection
        ]
        owner[field] = [payload] if field == "QC" else payload
    source = make_index(tmp_path, version, records)
    try:
        plan = sample_plan(
            source, str(owner["_id"]), review(), stage="related", collections={collection}
        )
        assert set(plan) <= {collection, "finding_comments"}
        assert len(plan[collection]) == 1
        assert plan[collection][0]["_id"] == payload["_id"]
        assert plan[collection][0]["SAMPLE_ID"] == str(owner["_id"])
        assert source.get("samples", str(owner["_id"])) == owner
        samples = sample_plan(source, str(owner["_id"]), review(), stage="samples")
        assert samples["samples"][0]["_id"] == owner["_id"]
    finally:
        source.close()


@pytest.mark.parametrize(
    "version,collection,physical", [(2, "fusions", "fusions"), (3, "d4_coverage", "panel_cov")]
)
def test_source_specific_related_collections(tmp_path, version, collection, physical):
    """Recorded fusion and D4 coverage payloads retain their IDs and sample ownership."""
    owner = sample()
    payload = read_json(
        Path(f"tests/fixtures/collections/all_collections_dummy/{collection}.json")
    )[0]
    payload.update(_id=ObjectId(), SAMPLE_ID=str(owner["_id"]))
    if collection == "d4_coverage":
        payload["sample"] = owner["name"]
    source = make_index(tmp_path, version, {"samples": [owner], physical: [payload]})
    try:
        plan = sample_plan(
            source, str(owner["_id"]), review(), stage="related", collections={collection}
        )
        assert plan[collection][0]["_id"] == payload["_id"]
        assert plan[collection][0]["SAMPLE_ID"] == str(owner["_id"])
    finally:
        source.close()


def test_related_selection_rejects_wrong_source_stage_and_unknown_collections():
    """Selectors cannot imply unsupported sources, include snapshots, or lose samples."""
    for version, stage, collections in (
        (2, "related", {"d4_coverage"}),
        (3, "related", {"fusions"}),
        (3, "related", {"variants"}),
        (3, "samples", {"cnvs"}),
        (3, "complete", {"cnvs"}),
        (3, "related", {"coverage"}),
        (3, "related", set()),
        (4, "related", {"cnvs"}),
        (3, "unknown-stage", None),
    ):
        with pytest.raises(ValueError):
            selected_collections(version, stage, collections)


@pytest.mark.parametrize("version", [2, 3])
def test_related_default_excludes_variants_and_sample_history(tmp_path, version):
    """Default related conversion includes supported types without reprocessing SNVs."""
    owner = sample()
    physical = "variants" if version == 3 else "variants_idref"
    source = make_index(
        tmp_path,
        version,
        {"samples": [owner], physical: [{"_id": ObjectId(), "SAMPLE_ID": str(owner["_id"])}]},
    )
    try:
        plan = sample_plan(source, str(owner["_id"]), review(), stage="related")
        assert (
            not {"variants", "samples", "reports", "annotation", "anno_vep", "reported_variants"}
            & plan.keys()
        )
    finally:
        source.close()


def test_related_qc_requires_review_for_multiple_recorded_results(tmp_path):
    """QC conversion cannot silently choose one of multiple historical results."""
    owner = sample()
    owner["QC"] = [{"unreviewed": True}, {"unreviewed": True}]
    source = make_index(tmp_path, 2, {"samples": [owner]})
    try:
        sample_plan(source, str(owner["_id"]), review(), stage="samples")
        with pytest.raises(ValueError, match="multiple entries"):
            sample_plan(
                source, str(owner["_id"]), review(), stage="related", collections={"rna_qc"}
            )
    finally:
        source.close()
