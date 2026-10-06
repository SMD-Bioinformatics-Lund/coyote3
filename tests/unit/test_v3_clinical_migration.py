"""Synthetic v3 history, identity, and non-destructive clinical migration cases."""

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from pydantic import ValidationError

from scripts.migration_common.clinical_plan import build_plan
from scripts.upgrade_from_v3.clinical_documents import (
    convert_annotation,
    convert_reported_variant,
    convert_sample,
)


def source_sample():
    """Return a v3-shaped synthetic sample with original report/comment identities."""
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return {
        "_id": ObjectId(),
        "name": "SYNTHETIC_V3",
        "case_id": "SYNTHETIC_V3",
        "sample_no": 1,
        "pipeline": "synthetic",
        "files": {"vcf_files": {"path": "/synthetic/findings.vcf.gz"}},
        "assay": "synthetic_group",
        "profile": "testing",
        "time_added": now,
        "report_num": 1,
        "comments": [
            {
                "_id": ObjectId(),
                "author": "synthetic_author",
                "text": "  preserved  ",
                "hidden": 1,
                "time_created": now,
            }
        ],
        "reports": [
            {
                "_id": ObjectId(),
                "report_num": 1,
                "report_id": "synthetic-report",
                "report_name": "synthetic-report.html",
                "filepath": "synthetic-report.html",
                "author": "synthetic_author",
                "time_created": now,
            }
        ],
    }


def metadata():
    """Return explicit new assay context without inventing historical attribution."""
    return {
        "asp_id": "synthetic_panel",
        "omics_layer": "dna",
        "sequencing_scope": "panel",
        "ingest_status": "ready",
        "current_aspc_id": "synthetic_revision",
    }


def test_sample_history_is_extracted_before_parent_validation():
    source = source_sample()
    original = deepcopy(source)
    sample, comments, reports = convert_sample(source, metadata())
    assert source == original
    assert sample["_id"] == source["_id"]
    assert sample["environment"] == "testing"
    assert "assay" not in sample and "reports" not in sample and "comments" not in sample
    assert sample["latest_report_id"] == source["reports"][0]["_id"]
    assert sample["ingested_by"] is None and sample["ingest_source"] is None
    assert comments[0]["_id"] == source["comments"][0]["_id"]
    assert comments[0]["text"] == "  preserved  " and comments[0]["hidden"] == 1
    assert reports[0]["filepath"] == source["reports"][0]["filepath"]


@pytest.mark.parametrize(
    "change",
    [
        {"report_num": 2},
        {"comments": None},
        {"reports": None},
        {"environment": "production"},
    ],
)
def test_inconsistent_history_or_scope_is_rejected(change):
    with pytest.raises((ValueError, ValidationError)):
        convert_sample({**source_sample(), **change}, metadata())


def test_assay_group_is_not_inferred_to_be_a_physical_panel():
    with pytest.raises(ValueError, match="explicit physical"):
        convert_sample(source_sample(), {})


@pytest.mark.parametrize(
    "nomenclature,variant,identity",
    [
        ("p", "ENSP_SYNTHETIC:p.Val1Ala", "hgvsp"),
        ("c", "ENST_SYNTHETIC:c.1T>C", "hgvsc"),
        ("g", "1_100_A_T", "genomic"),
    ],
)
def test_annotations_preserve_scope_author_and_class(nomenclature, variant, identity):
    source = {
        "_id": ObjectId(),
        "assay": "synthetic_group",
        "subpanel": "base",
        "nomenclature": nomenclature,
        "variant": variant,
        "gene": "SYNTHETIC",
        "transcript": None,
        "author": "synthetic_author",
        "class": 2,
        "time_created": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    result = convert_annotation(source)
    assert result[identity] == variant
    for key in ("_id", "variant", "class", "author", "time_created", "assay", "subpanel"):
        assert result[key] == source[key]


def test_orphan_finding_is_rejected_before_copy():
    with pytest.raises(ValueError, match="absent sample"):
        build_plan({"variants": [{"_id": ObjectId(), "SAMPLE_ID": str(ObjectId())}]}, {})


def test_missing_comment_identity_is_not_replaced_with_a_new_identity():
    source = source_sample()
    source["comments"][0].pop("_id")
    with pytest.raises(ValueError, match="original _id"):
        convert_sample(source, metadata())


def test_finding_comments_and_vep_evidence_keep_their_original_context():
    sample = source_sample()
    sample["vep_version"] = "110"
    transcript = {"Feature": "ENST_SYNTHETIC", "Consequence": "missense_variant"}
    variant = {
        "_id": ObjectId(),
        "SAMPLE_ID": str(sample["_id"]),
        "CHROM": "1",
        "POS": 100,
        "REF": "A",
        "ALT": "T",
        "ID": ".",
        "simple_id": "1_100_A_T",
        "INFO": {
            "CSQ": [transcript],
            "selected_CSQ": transcript,
            "selected_CSQ_criteria": "original selection",
        },
        "comments": deepcopy(sample["comments"]),
    }
    sources = {"samples": [sample], "variants": [variant]}
    plan = build_plan(sources, {str(sample["_id"]): metadata()})
    assert plan["finding_comments"][0]["finding_oid"] == variant["_id"]
    assert plan["finding_comments"][0]["sample_oid"] == sample["_id"]
    assert "comments" not in plan["variants"][0]
    assert plan["variants"][0]["INFO"]["selected_CSQ_criteria"] == "original selection"
    assert plan["anno_vep"][0]["vep_version"] == "110"
    assert plan["anno_vep"][0]["CSQ"][0]["Feature"] == "ENST_SYNTHETIC"
    assert build_plan(sources, {str(sample["_id"]): metadata()}) == plan
    sample.pop("vep_version")
    with pytest.raises(ValueError, match="Original VEP version"):
        build_plan(sources, {str(sample["_id"]): metadata()})


def test_legacy_reported_variant_retains_report_time_tier_and_text():
    sample_id, variant_id = ObjectId(), ObjectId()
    variant = {"_id": variant_id, "SAMPLE_ID": str(sample_id), "simple_id": "1_100_A_T"}
    snapshot = {
        "_id": ObjectId(),
        "var_oid": variant_id,
        "sample_oid": sample_id,
        "sample_name": "SYNTHETIC_V3",
        "report_oid": ObjectId(),
        "report_id": "synthetic-report",
        "simple_id": "1_100_A_T",
        "simple_id_hash": None,
        "tier": 2,
        "text": "Original report text",
        "created_by": "synthetic_author",
        "created_on": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    result = convert_reported_variant(snapshot, variant)
    assert result["analysis_type"] == "SNV" and result["finding_type"] == "small_variant"
    assert result["tier"] == 2 and result["text"] == snapshot["text"]
    assert result["created_on"] == snapshot["created_on"]
    variant["SAMPLE_ID"] = str(ObjectId())
    with pytest.raises(ValueError, match="original small variant"):
        convert_reported_variant(snapshot, variant)
