"""Operator-supplied historical annotation scopes use migration-only mappings."""

from copy import deepcopy
from datetime import datetime

import pytest
from bson import ObjectId

from scripts.migration_common.clinical_plan import build_plan
from scripts.migration_common.conversion import independent_plan
from scripts.migration_common.target_catalog import validate_plan_scope
from scripts.upgrade_from_v3.clinical_documents import convert_annotation
from tests.unit.test_offline_legacy_migrations import make_index


def annotation(assay, subpanel):
    """Return a synthetic annotation with independently preserved clinical content."""
    return {
        "_id": ObjectId(),
        "assay": assay,
        "subpanel": subpanel,
        "nomenclature": "p",
        "variant": "p.Synthetic",
        "gene": "SYNTHETIC",
        "transcript": "SYNTHETIC.1",
        "class": 2,
        "author": "Synthetic Reviewer",
        "time_created": datetime(2025, 1, 1),
    }


@pytest.mark.parametrize(
    "assay,asp,subpanels",
    [
        ("gmsonco", None, {"other": "other"}),
        (
            "hematology",
            "hema_gmsv1",
            {
                "": "",
                "AlloSCT": "allosct",
                "Hem": "hem",
                "Hem-Snabb": "hem-snabb",
                "KLL": "kll",
                "MPN": "mpn",
                "Riktad": "riktad",
                "other": "other",
            },
        ),
        ("lymphoid", None, {"other": "other"}),
        (
            "myeloid",
            "myeloid_gmsv1",
            {
                "AlloSCT": "allosct",
                "Hem": "hem",
                "Hem-Snabb": "hem-snabb",
                "KLL": "kll",
                "MPN": "mpn",
                "None": "none",
                "Riktad": "riktad",
            },
        ),
        (
            "solid",
            "solid_gmsv3",
            {
                "BC": "breast",
                "BP": "breast-pilot",
                "CRC": "crc",
                "LP": "lung",
                "None": "base",
                "breast": "breast",
                "cns": "cns",
                "colon": "colon",
                "endometrie": "endometrie",
                "gist": "gist",
                "lungthyroid": "lungthyroid",
                "melanoma": "melanoma",
                "ovarian": "ovarian",
                "solid": "base",
            },
        ),
        ("tumwgs", None, {"": "", "None": "none"}),
        ("unknown", None, {"other": "other"}),
    ],
)
@pytest.mark.parametrize("version", [2, 3])
def test_annotation_scope_mapping_for_both_exports(tmp_path, version, assay, asp, subpanels):
    """Both migration entry paths preserve content and apply every supplied scope pair."""
    originals = [annotation(assay, subpanel) for subpanel in subpanels]
    source = make_index(tmp_path, version, {"annotation": originals})
    try:
        rows = independent_plan(source, "annotation", {})["annotation"]
        by_id = {row["_id"]: row for row in rows}
        for original in originals:
            expected = deepcopy(original)
            converted = by_id[original["_id"]]
            assert converted["asp_group"] == assay
            assert converted["asp_id"] == asp
            assert converted["diagnosis_id"] == subpanels[original["subpanel"]]
            assert "assay" not in converted and "subpanel" not in converted
            for field in (
                "_id",
                "variant",
                "gene",
                "transcript",
                "class",
                "author",
                "time_created",
            ):
                assert converted[field] == original[field]
            assert source.get("annotation", str(original["_id"])) == expected
    finally:
        source.close()


def test_uppercase_scope_and_explicit_asp_are_normalized_without_touching_content():
    """Only scope identifiers are lowercased, including an explicitly recorded ASP."""
    source = annotation("SOLID", "BC")
    source["asp_id"] = "solid_GMSv3"
    result = convert_annotation(source)
    assert (result["asp_group"], result["asp_id"], result["diagnosis_id"]) == (
        "solid",
        "solid_gmsv3",
        "breast",
    )
    assert result["author"] == "Synthetic Reviewer"
    source["asp_id"] = "different_panel"
    with pytest.raises(ValueError, match="conflicts"):
        convert_annotation(source)


def test_missing_annotation_scope_is_not_invented():
    """The empty grouped identity provides no evidence for assigning a scope."""
    source = annotation(None, None)
    source.pop("assay")
    source.pop("subpanel")
    with pytest.raises(ValueError):
        convert_annotation(source)


def test_shared_sample_plan_converter_uses_the_same_annotation_scope_mapping():
    """Report-linked annotations receive the same mapping as standalone annotations."""
    original = annotation("hematology", "AlloSCT")
    row = build_plan({"annotation": [original]}, {})["annotation"][0]
    assert row["asp_id"] == "hema_gmsv1"
    assert row["diagnosis_id"] == "allosct"
    assert row["_id"] == original["_id"]


def test_annotation_target_validation_uses_mapped_group_asp_and_diagnosis():
    """A mapped annotation must match an installed ASP and diagnosis association."""
    row = convert_annotation(annotation("solid", "BC"))
    records = {
        "assay_groups": [{"group_id": "solid"}],
        "assay_specific_panels": [{"asp_id": "solid_gmsv3", "asp_group": "solid"}],
        "diagnoses": [{"diagnosis_id": "breast"}],
        "diagnosis_associations": [{"asp_id": "solid_gmsv3", "diagnosis_id": "breast"}],
    }
    validate_plan_scope({"collections": records}, {"annotation": [row]})
    records["diagnosis_associations"] = []
    with pytest.raises(ValueError, match="association"):
        validate_plan_scope({"collections": records}, {"annotation": [row]})
    records["assay_specific_panels"] = []
    with pytest.raises(ValueError, match="ASP"):
        validate_plan_scope({"collections": records}, {"annotation": [row]})
