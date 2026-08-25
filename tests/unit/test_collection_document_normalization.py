"""Regression tests for MongoDB collection and embedded document boundaries."""

import pytest

from api.contracts.schemas.registry import normalize_collection_document


def test_normalization_omits_null_ids_from_embedded_documents() -> None:
    normalized = normalize_collection_document(
        "samples",
        {
            "name": "sample_1",
            "asp_id": "assay_1",
            "subpanel_id": "base",
            "environment": "testing",
            "case_id": "case_1",
            "sample_no": 1,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "TestPipeline",
            "files": {"vcf_files": {"path": "/data/sample.vcf"}},
            "filters": {"somatic": {"snv": {}}},
        },
    )

    assert "_id" not in normalized
    assert "_id" not in normalized["files"]["vcf_files"]
    assert "_id" not in normalized["filters"]
    assert "_id" not in normalized["filters"]["somatic"]
    assert "_id" not in normalized["filters"]["somatic"]["snv"]


def test_normalization_preserves_real_mongo_ids() -> None:
    normalized = normalize_collection_document(
        "permissions",
        {
            "_id": "permission-document-id",
            "permission_id": "sample:view",
            "label": "View samples",
            "category": "Sample Management",
            "description": "View samples.",
            "tags": ["sample", "view"],
        },
    )

    assert normalized["_id"] == "permission-document-id"


def test_embedded_documents_reject_mongo_ids() -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        normalize_collection_document(
            "samples",
            {
                "name": "sample_1",
                "asp_id": "assay_1",
                "subpanel_id": "base",
                "environment": "testing",
                "case_id": "case_1",
                "sample_no": 1,
                "sequencing_scope": "panel",
                "omics_layer": "dna",
                "pipeline": "TestPipeline",
                "filters": {"_id": None, "somatic": {"snv": {}}},
            },
        )


def test_annotation_normalization_omits_unrelated_and_inactive_fields() -> None:
    normalized = normalize_collection_document(
        "annotation",
        {
            "variant": "p.Arg175His",
            "hgvsp": "p.Arg175His",
            "hgvsc": "c.524G>A",
            "genomic": "17_7675088_C_T",
            "genomic_hash": "hash",
            "gene": "TP53",
            "transcript": None,
            "assay": "solid",
            "subpanel": "base",
            "author": "reviewer",
            "nomenclature": "p",
            "class": 2,
        },
    )

    assert normalized["class"] == 2
    assert "text" not in normalized
    assert normalized["transcript"] is None
    assert "cnv" not in normalized
    assert "gene1" not in normalized


def test_annotation_contract_rejects_incomplete_small_variant_identity() -> None:
    with pytest.raises(ValueError, match="requires"):
        normalize_collection_document(
            "annotation",
            {
                "variant": "p.Arg175His",
                "hgvsp": "p.Arg175His",
                "gene": "TP53",
                "assay": "solid",
                "subpanel": "base",
                "author": "reviewer",
                "nomenclature": "p",
                "class": 2,
            },
        )


def test_annotation_contract_preserves_present_nullable_small_variant_identities() -> None:
    normalized = normalize_collection_document(
        "annotation",
        {
            "variant": "p.Arg175His",
            "hgvsp": "p.Arg175His",
            "hgvsc": None,
            "genomic": None,
            "genomic_hash": None,
            "gene": "TP53",
            "assay": "solid",
            "subpanel": "base",
            "author": "reviewer",
            "nomenclature": "p",
            "class": 2,
        },
    )

    assert normalized["hgvsp"] == "p.Arg175His"
    assert normalized["hgvsc"] is None
    assert normalized["genomic"] is None
    assert normalized["genomic_hash"] is None
    assert normalized["gene"] == "TP53"
    assert "text" not in normalized


def test_annotation_contract_rejects_unrelated_identity_field() -> None:
    with pytest.raises(ValueError, match="does not allow: fusion"):
        normalize_collection_document(
            "annotation",
            {
                "variant": "p.Arg175His",
                "hgvsp": "p.Arg175His",
                "hgvsc": "c.524G>A",
                "genomic": "17_7675088_C_T",
                "genomic_hash": "hash",
                "gene": "TP53",
                "fusion": "EML4^ALK",
                "assay": "solid",
                "subpanel": "base",
                "author": "reviewer",
                "nomenclature": "p",
                "class": 2,
            },
        )


def test_annotation_contract_rejects_null_unrelated_identity_field() -> None:
    with pytest.raises(ValueError, match="does not allow: fusion"):
        normalize_collection_document(
            "annotation",
            {
                "variant": "p.Arg175His",
                "hgvsp": "p.Arg175His",
                "hgvsc": "c.524G>A",
                "genomic": "17_7675088_C_T",
                "genomic_hash": "hash",
                "gene": "TP53",
                "fusion": None,
                "assay": "solid",
                "subpanel": "base",
                "author": "reviewer",
                "nomenclature": "p",
                "class": 2,
            },
        )


def test_annotation_contract_rejects_class_and_text_together() -> None:
    with pytest.raises(ValueError, match="Exactly one"):
        normalize_collection_document(
            "annotation",
            {
                "variant": "7:10-20",
                "assay": "solid",
                "subpanel": "base",
                "author": "reviewer",
                "nomenclature": "cn",
                "class": 2,
                "text": "conflicting payload",
            },
        )


@pytest.mark.parametrize(
    ("nomenclature", "identity", "unrelated_field"),
    [
        ("cn", {"variant": "7:10-20"}, "cnv"),
        ("cn", {"variant": "7:10-20"}, "gene"),
        (
            "f",
            {"variant": "EML4^ALK", "gene1": "EML4", "gene2": "ALK"},
            "fusion",
        ),
        (
            "t",
            {"variant": "1:100^2:200", "gene1": "GENE1", "gene2": "GENE2"},
            "translocation",
        ),
    ],
)
def test_annotation_structural_contract_rejects_legacy_fields_even_when_null(
    nomenclature: str,
    identity: dict,
    unrelated_field: str,
) -> None:
    with pytest.raises(ValueError, match=f"does not allow: {unrelated_field}"):
        normalize_collection_document(
            "annotation",
            {
                **identity,
                unrelated_field: None,
                "assay": "global",
                "subpanel": "base",
                "author": "reviewer",
                "nomenclature": nomenclature,
                "text": "reviewed",
            },
        )


@pytest.mark.parametrize(
    ("nomenclature", "identity"),
    [
        ("cn", {"variant": "7:10-20"}),
        (
            "f",
            {
                "variant": "EML4^ALK",
                "gene1": "EML4",
                "gene2": "ALK",
            },
        ),
        (
            "t",
            {
                "variant": "1:100^2:200",
                "gene1": "GENE1",
                "gene2": "GENE2",
            },
        ),
    ],
)
def test_annotation_structural_shapes_contain_only_applicable_fields(
    nomenclature: str, identity: dict
) -> None:
    normalized = normalize_collection_document(
        "annotation",
        {
            **identity,
            "assay": "global",
            "subpanel": "base",
            "author": "reviewer",
            "nomenclature": nomenclature,
            "text": "reviewed",
        },
    )

    assert normalized["text"] == "reviewed"
    assert "class" not in normalized
    all_specific_fields = {
        "hgvsp",
        "hgvsc",
        "genomic",
        "genomic_hash",
        "cnv",
        "fusion",
        "translocation",
        "gene",
        "gene1",
        "gene2",
        "transcript",
    }
    for field in all_specific_fields - set(identity):
        assert field not in normalized
