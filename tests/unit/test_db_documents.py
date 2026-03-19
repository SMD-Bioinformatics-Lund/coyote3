"""Tests for core DB document contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.contracts.db_documents import (
    VariantsDoc,
    supported_collections,
    validate_collection_document,
)


def test_variant_info_accepts_selected_csq_aliases():
    """INFO should accept selectedCSQ camelCase alias and parse nested CSQ docs."""
    payload = {
        "SAMPLE_ID": "S1",
        "CHROM": "1",
        "POS": 100,
        "REF": "A",
        "ALT": "G",
        "INFO": {
            "variant_callers": ["tnscope"],
            "CSQ": [{"Feature": "ENST1", "SYMBOL": "TP53"}],
            "selectedCSQ": {"Feature": "ENST1", "SYMBOL": "TP53"},
            "selectedCSQCriteria": "db",
        },
    }
    doc = VariantsDoc.model_validate(payload)
    assert doc.INFO.CSQ[0].SYMBOL == "TP53"
    assert doc.INFO.selected_CSQ is not None
    assert doc.INFO.selected_CSQ.SYMBOL == "TP53"
    assert doc.INFO.selected_CSQ_criteria == "db"


def test_variant_info_normalizes_variant_callers_string():
    """variant_callers pipe-separated string should normalize to list[str]."""
    payload = {
        "SAMPLE_ID": "S1",
        "CHROM": "1",
        "POS": 100,
        "REF": "A",
        "ALT": "G",
        "INFO": {
            "variant_callers": "tnscope|strelka",
            "csq": [{"Feature": "ENST1", "SYMBOL": "TP53"}],
        },
    }
    doc = VariantsDoc.model_validate(payload)
    assert doc.INFO.variant_callers == ["tnscope", "strelka"]
    assert len(doc.INFO.CSQ) == 1


def test_collection_validator_accepts_hgnc_genes_shape():
    """hgnc_genes collection should validate core fields."""
    validate_collection_document(
        "hgnc_genes",
        {
            "hgnc_id": "HGNC:5",
            "hgnc_symbol": "A1BG",
            "gene_name": "alpha-1-B glycoprotein",
            "extra_runtime_key": "ok",
        },
    )


def test_collection_validator_accepts_oncokb_alias_field():
    """OncoKB actionable docs should parse source key casing."""
    validate_collection_document("oncokb_actionable", {"Alteration": "BRAF V600E"})


def test_collection_validator_accepts_nested_sample_shape():
    """samples collection should validate nested case/control/filter/comment/report blocks."""
    validate_collection_document(
        "samples",
        {
            "name": "S1",
            "assay": "hema_GMSv1",
            "profile": "prod",
            "case_id": "S1",
            "sample_no": 1,
            "sequencing_technology": "Illumina",
            "pipeline": "SomaticPanelPipeline",
            "pipeline_version": "3.1.14",
            "filters": {"max_freq": 0.1, "vep_consequences": ["missense_variant"]},
            "case": {"id": "S1", "reads": 1000},
            "comments": [{"author": "a", "text": "ok"}],
            "reports": [{"report_id": "R1", "report_num": 1}],
        },
    )


def test_collection_validator_accepts_nested_panel_cov_shape():
    """panel_cov collection should validate nested gene coverage hierarchy."""
    validate_collection_document(
        "panel_cov",
        {
            "SAMPLE_ID": "S1",
            "sample": "S1",
            "genes": {
                "TP53": {
                    "CDS": {
                        "17_7577121_7577190": {
                            "chr": "17",
                            "start": "7577121",
                            "end": "7577190",
                            "nbr": "122",
                        }
                    }
                }
            },
        },
    )


def test_supported_collections_exposes_expected_core_names():
    """Supported ingest collection list should include core center-seeded collections."""
    names = supported_collections()
    for required in (
        "permissions",
        "roles",
        "users",
        "asp_configs",
        "assay_specific_panels",
        "insilico_genelists",
        "refseq_canonical",
        "hgnc_genes",
    ):
        assert required in names


def test_collection_validator_rejects_invalid_aspc_id_environment_mismatch():
    """asp_configs must keep aspc_id aligned with assay_name/environment fields."""
    with pytest.raises(ValueError):
        validate_collection_document(
            "asp_configs",
            {
                "aspc_id": "ASSAY_A:production",
                "assay_name": "ASSAY_A",
                "environment": "development",
                "asp_group": "GROUP_A",
            },
        )


def test_collection_validator_rejects_user_without_role():
    """users contract requires role and normalized environment values."""
    with pytest.raises(ValueError):
        validate_collection_document(
            "users",
            {
                "email": "admin@center.local",
                "environments": ["prod"],
            },
        )


def test_collection_validator_accepts_all_collections_dummy_fixture():
    """Every collection document in all_collections_dummy should pass validation."""
    payload = json.loads(
        Path("tests/fixtures/db_dummy/all_collections_dummy.json").read_text(encoding="utf-8")
    )
    for collection, docs in payload.items():
        for doc in docs:
            validate_collection_document(collection, doc)
