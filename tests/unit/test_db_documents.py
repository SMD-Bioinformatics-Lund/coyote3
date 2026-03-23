"""Tests for core DB document contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from api.contracts.schemas.dna import VariantsDoc
from api.contracts.schemas.registry import supported_collections, validate_collection_document


def test_variant_info_accepts_selected_csq_fields():
    """INFO should parse nested CSQ docs and selected-CSQ fields."""
    payload = {
        "SAMPLE_ID": "S1",
        "CHROM": "1",
        "POS": 100,
        "REF": "A",
        "ALT": "G",
        "ID": ".",
        "QUAL": 99.0,
        "INFO": {
            "variant_callers": ["tnscope"],
            "CSQ": [{"Feature": "ENST1", "SYMBOL": "TP53"}],
            "selected_CSQ": {"Feature": "ENST1", "SYMBOL": "TP53"},
            "selected_CSQ_criteria": "db",
        },
        "simple_id": "1_100_A_G",
        "simple_id_hash": hashlib.md5("1_100_A_G".encode("utf-8")).hexdigest(),
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
        "ID": ".",
        "QUAL": 99.0,
        "INFO": {
            "variant_callers": "tnscope|strelka",
            "CSQ": [{"Feature": "ENST1", "SYMBOL": "TP53"}],
            "selected_CSQ": {"Feature": "ENST1", "SYMBOL": "TP53"},
            "selected_CSQ_criteria": "db",
        },
        "simple_id": "1_100_A_G",
        "simple_id_hash": hashlib.md5("1_100_A_G".encode("utf-8")).hexdigest(),
    }
    doc = VariantsDoc.model_validate(payload)
    assert doc.INFO.variant_callers == ["tnscope", "strelka"]
    assert len(doc.INFO.CSQ) == 1


def test_collection_validator_accepts_hgnc_genes_shape():
    """hgnc_genes strict model should accept the curated fixture shape."""
    fixture = Path("tests/fixtures/db_dummy/all_collections_dummy/hgnc_genes.json")
    payload = json.loads(fixture.read_text(encoding="utf-8"))[0]
    validate_collection_document("hgnc_genes", payload)


def test_collection_validator_accepts_oncokb_actionable_shape():
    """OncoKB actionable strict model should accept curated fixture docs."""
    fixture = Path("tests/fixtures/db_dummy/all_collections_dummy/oncokb_actionable.json")
    payload = json.loads(fixture.read_text(encoding="utf-8"))[0]
    validate_collection_document("oncokb_actionable", payload)


def test_collection_validator_accepts_nested_sample_shape():
    """samples collection should validate nested case/control/filter/comment/report blocks."""
    fixture = Path("tests/fixtures/db_dummy/all_collections_dummy/samples.json")
    payload = json.loads(fixture.read_text(encoding="utf-8"))[0]
    validate_collection_document("samples", payload)


def test_collection_validator_rejects_dna_sample_with_rna_keys():
    """DNA sample payload must not include RNA-only file keys."""
    with pytest.raises(ValueError):
        validate_collection_document(
            "samples",
            {
                "name": "S1",
                "assay": "hema_GMSv1",
                "profile": "prod",
                "case_id": "S1",
                "sample_no": 1,
                "omics_layer": "DNA",
                "vcf_files": "/data/dna.vcf.gz",
                "fusion_files": "/data/rna.fusions.json",
            },
        )


def test_collection_validator_rejects_rna_sample_with_dna_keys():
    """RNA sample payload must not include DNA-only file keys."""
    with pytest.raises(ValueError):
        validate_collection_document(
            "samples",
            {
                "name": "S1",
                "assay": "fusion_assay",
                "profile": "prod",
                "case_id": "S1",
                "sample_no": 1,
                "omics_layer": "RNA",
                "fusion_files": "/data/rna.fusions.json",
                "vcf_files": "/data/dna.vcf.gz",
            },
        )


def test_collection_validator_accepts_nested_panel_coverage_shape():
    """panel_coverage strict model should accept curated fixture docs."""
    fixture = Path("tests/fixtures/db_dummy/all_collections_dummy/panel_coverage.json")
    payload = json.loads(fixture.read_text(encoding="utf-8"))[0]
    validate_collection_document("panel_coverage", payload)


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
                "email": "admin@your-center.org",
                "environments": ["prod"],
            },
        )


def test_collection_validator_accepts_strict_ready_fixture_subset():
    """Strict-ready fixture collections should pass validation end-to-end."""
    fixture_dir = Path("tests/fixtures/db_dummy/all_collections_dummy")
    payload = {
        file.stem: json.loads(file.read_text(encoding="utf-8"))
        for file in sorted(fixture_dir.glob("*.json"))
    }
    strict_ready = {
        "cnvs",
        "mane_select",
        "oncokb_genes",
        "permissions",
        "refseq_canonical",
        "roles",
        "samples",
    }
    for collection in strict_ready:
        docs = payload[collection]
        for doc in docs:
            validate_collection_document(collection, doc)
