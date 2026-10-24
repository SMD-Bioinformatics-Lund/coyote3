"""Pinned resource content remains stable and fails closed when invalid."""

from copy import deepcopy

import pytest
from bson import ObjectId

from api.application.common.release_resources import (
    assay_resource,
    capture_assay_resource,
    capture_gene_lists,
    gene_list_resources,
)
from api.application.reporting.resolution_receipt import report_resolution_receipt
from api.domain.core.exceptions import AppError


def test_assay_revision_is_independent_of_authoring_and_runtime_edits():
    panel = {
        "_id": ObjectId(),
        "asp_id": "demo-solid_gmsv3",
        "asp_group": "solid",
        "version": 1,
        "covered_genes": {"TP53": True},
    }
    configuration = {
        "asp_id": "demo-solid_gmsv3",
        "asp_group": "solid",
        "assay_resource_release": capture_assay_resource(panel),
    }
    panel["covered_genes"]["BRAF"] = True
    loaded = assay_resource(configuration)
    assert loaded["covered_genes"] == {"TP53": True}
    loaded["covered_genes"].clear()
    assert assay_resource(configuration)["covered_genes"] == {"TP53": True}


@pytest.mark.parametrize("field", ["asp_id", "asp_group"])
def test_valid_resource_hash_does_not_allow_wrong_configuration_identity(field):
    panel = {"asp_id": "demo-solid_gmsv3", "asp_group": "solid"}
    configuration = {**panel, "assay_resource_release": capture_assay_resource(panel)}
    configuration[field] = "different"
    with pytest.raises(AppError, match="does not match"):
        assay_resource(configuration)


def test_altered_assay_or_gene_list_content_is_rejected():
    panel = {"asp_id": "demo-solid_gmsv3", "asp_group": "solid"}
    configuration = {**panel, "assay_resource_release": capture_assay_resource(panel)}
    configuration["assay_resource_release"]["content"]["version"] = 10
    with pytest.raises(AppError, match="invalid hash"):
        assay_resource(configuration)
    configuration["gene_list_release"] = capture_gene_lists(
        [{"isgl_id": "breast", "version": 2, "genes": ["TP53"]}]
    )
    configuration["gene_list_release"]["content"]["breast"]["genes"].append("BRAF")
    with pytest.raises(AppError, match="invalid hash"):
        gene_list_resources(configuration)


def test_list_selection_distinguishes_all_none_and_unavailable():
    documents = [{"isgl_id": "breast", "version": 2, "genes": ["TP53"]}]
    original = deepcopy(documents)
    configuration = {"gene_list_release": capture_gene_lists(documents)}
    documents[0]["genes"].append("BRAF")
    assert gene_list_resources(configuration) == {"breast": original[0]}
    assert gene_list_resources(configuration, []) == {}
    assert gene_list_resources(configuration, ["breast"]) == {"breast": original[0]}
    with pytest.raises(AppError, match="not available"):
        gene_list_resources(configuration, ["unregistered"])
    with pytest.raises(AppError, match="Multiple selectable revisions"):
        capture_gene_lists([original[0], {**original[0], "version": 3}])


def test_report_receipt_freezes_scope_overrides_and_input_lineage():
    panel = {
        "asp_id": "demo-solid_gmsv3",
        "asp_group": "solid",
        "covered_genes": ["TP53"],
    }
    configuration = {
        "asp_id": "demo-solid_gmsv3",
        "asp_group": "solid",
        "assay_resource_release": capture_assay_resource(panel),
        "gene_list_release": capture_gene_lists(
            [
                {
                    "isgl_id": "breast",
                    "version": 2,
                    "list_type": ["snv"],
                    "is_active": True,
                    "genes": ["TP53", "BRAF"],
                }
            ]
        ),
        "filters": {"somatic": {"snv": {"min_depth": 30, "snvlists": ["breast"]}}},
        "reporting": {"language": "sv"},
    }
    sample = {
        "version": 7,
        "environment": "validation",
        "asp_category": "dna",
        "pipeline": "SyntheticFixture",
        "pipeline_version": "1.0",
        "genome_build": 38,
        "files": {"vcf_files": {"path": "/synthetic/input.vcf"}},
        "filters": {"somatic": {"snv": {"min_depth": 100, "snvlists": ["breast"]}}},
    }
    receipt = report_resolution_receipt(
        "dna_report.html", {"sample": sample, "assay_config": configuration}
    )
    assert receipt["gene_scopes"]["somatic:snv"]["genes"] == ["TP53"]
    assert receipt["gene_scopes"]["somatic:snv"]["excluded"] == [
        {"gene": "BRAF", "reason": "outside_assay_eligibility"}
    ]
    assert receipt["filters"]["overrides"] == [
        {
            "intent": "somatic",
            "analysis": "snv",
            "field": "min_depth",
            "default": 30,
            "effective": 100,
        }
    ]
    assert receipt["pipeline"] == {"name": "SyntheticFixture", "version": "1.0"}
    sample["files"]["vcf_files"]["path"] = "/synthetic/replacement.vcf"
    sample["filters"]["somatic"]["snv"]["min_depth"] = 10
    assert receipt["input_files"]["vcf_files"]["path"] == "/synthetic/input.vcf"
    assert receipt["filters"]["effective"]["somatic"]["snv"]["min_depth"] == 100
