"""Tests for core DB document contracts."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from api.contracts.managed_resources import managed_resource_spec
from api.contracts.managed_ui_schemas import build_form_spec
from api.contracts.schemas.dna import VariantsDoc
from api.contracts.schemas.governance import UsersDoc
from api.contracts.schemas.registry import (
    normalize_collection_document,
    supported_collections,
    validate_collection_document,
)
from api.contracts.schemas.samples import SampleCaseControlDoc, SamplesDoc


def _load_seed_list(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_reference_seed_list(filename: str) -> list[dict]:
    base = Path("tests/data/seed_data")
    path = base / filename
    if not path.exists() and filename.endswith(".gz"):
        plain_name = filename[:-3]
        plain_path = base / plain_name
        if plain_path.exists():
            path = plain_path
    docs: list[dict] = []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                docs.append(json.loads(text))
    return docs


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
    payload = _load_reference_seed_list("hgnc_genes.seed.ndjson.gz")[0]
    validate_collection_document("hgnc_genes", payload)


def test_collection_validator_accepts_vep_metadata_with_grouped_consequences():
    """vep_metadata strict model should accept grouped consequence metadata."""
    payload = _load_reference_seed_list("vep_metadata.seed.ndjson.gz")[0]
    validate_collection_document("vep_metadata", payload)
    normalized = normalize_collection_document("vep_metadata", payload)
    assert normalized["vep_id"] == "103"
    consequence = payload["conseq_translations"]["missense_variant"]
    assert consequence["group"] == "missense"
    assert "missense_variant" in payload["consequence_groups"]["missense"]


def test_collection_validator_rejects_vep_groups_with_unknown_terms():
    """vep_metadata grouped terms must exist in conseq_translations for that version."""
    payload = _load_reference_seed_list("vep_metadata.seed.ndjson.gz")[0]
    payload["consequence_groups"]["missense"] = ["missense_variant", "not_a_real_term"]

    with pytest.raises(ValueError, match="unknown consequence terms"):
        validate_collection_document("vep_metadata", payload)


def test_collection_validator_accepts_oncokb_actionable_shape():
    """OncoKB actionable strict model should accept curated fixture docs."""
    fixture = Path("tests/fixtures/db_dummy/all_collections_dummy/oncokb_actionable.json")
    payload = _load_seed_list(fixture)[0]
    validate_collection_document("oncokb_actionable", payload)


def test_collection_validator_accepts_nested_sample_shape():
    """samples collection should validate nested case/control/filter/comment/report blocks."""
    fixture = Path("tests/fixtures/db_dummy/all_collections_dummy/samples.json")
    payload = _load_seed_list(fixture)[0]
    validate_collection_document("samples", payload)


def test_samples_doc_keeps_filters_unset_until_initialized():
    """SamplesDoc should leave filters unset until sample defaults are materialized elsewhere."""
    dna_doc = SamplesDoc.model_validate(
        {
            "name": "S1",
            "assay": "assay_1",
            "subpanel": "hem",
            "profile": "production",
            "case_id": "CASE_DEMO",
            "sample_no": 1,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "SomaticPanelPipeline",
            "pipeline_version": "1.0.0",
            "vcf_files": "x",
        }
    )
    assert dna_doc.filters is None
    assert isinstance(dna_doc.case, SampleCaseControlDoc)
    assert "filters" not in dna_doc.model_dump(exclude_none=True)

    rna_doc = SamplesDoc.model_validate(
        {
            "name": "S2",
            "assay": "fusion_assay",
            "subpanel": "rna",
            "profile": "production",
            "case_id": "CASE_RNA",
            "sample_no": 1,
            "sequencing_scope": "wts",
            "omics_layer": "rna",
            "pipeline": "RnaPipeline",
            "pipeline_version": "1.0.0",
            "fusion_files": "x",
        }
    )
    assert rna_doc.filters is None
    assert isinstance(rna_doc.case, SampleCaseControlDoc)


def test_collection_validator_rejects_dna_sample_with_rna_keys():
    """DNA sample payload must not include RNA-only file keys."""
    with pytest.raises(ValueError):
        validate_collection_document(
            "samples",
            {
                "name": "S1",
                "assay": "assay_1",
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
    payload = _load_seed_list(fixture)[0]
    validate_collection_document("panel_coverage", payload)


def test_users_doc_rejects_non_canonical_username_characters():
    """Users must use canonical login ids, not whitespace or arbitrary symbols."""
    with pytest.raises(ValueError, match="username may contain only"):
        UsersDoc.model_validate(
            {
                "email": "tester@example.com",
                "username": "Åsa Test",
                "firstname": "Åsa",
                "lastname": "Test",
                "fullname": "Åsa Test",
                "job_title": "Scientist",
            }
        )


def test_managed_user_form_exposes_environment_options_and_username_readonly_on_edit():
    """User form metadata should expose fixed environment choices and edit-time username lock."""
    form = build_form_spec(managed_resource_spec("user"))
    assert form["fields"]["environments"]["options"] == [
        "production",
        "development",
        "testing",
        "validation",
    ]
    assert form["fields"]["username"]["readonly_mode"] == ["edit"]


def test_managed_isgl_form_uses_predefined_list_type_choices():
    """ISGL list types should be selected from fixed choices, not free text."""
    form = build_form_spec(managed_resource_spec("isgl"))
    assert form["fields"]["list_type"]["display_type"] == "checkbox-group"
    assert form["fields"]["list_type"]["options"] == [
        "small_variant_genelist",
        "cnv_genelist",
        "fusion_genelist",
    ]


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
                "aspc_id": "assay_1:production",
                "assay_name": "assay_1",
                "environment": "development",
                "asp_group": "hematology",
            },
        )


def test_collection_validator_normalizes_aspc_analysis_aliases():
    """asp_configs should normalize biomarker-related and CNV-profile aliases."""
    payload = normalize_collection_document(
        "asp_configs",
        {
            "aspc_id": "assay_1:development",
            "assay_name": "assay_1",
            "environment": "development",
            "asp_group": "hematology",
            "asp_category": "dna",
            "analysis_types": ["snv", "tmb", "pgx", "cnv profile"],
            "display_name": "Assay 1 Dev",
            "filters": {"vep_consequences": ["missense"], "cnveffects": ["gain", "loss"]},
            "query": {},
            "reporting": {
                "report_sections": ["tmb", "cnv-profile"],
                "report_header": "Header",
                "report_method": "Method",
                "report_description": "Description",
                "general_report_summary": "Summary",
                "plots_path": "/tmp",
                "report_folder": "reports",
            },
        },
    )

    assert payload["analysis_types"] == ["SNV", "TMB", "PGX", "CNV_PROFILE"]
    assert payload["reporting"]["report_sections"] == ["TMB", "CNV_PROFILE"]


def test_collection_validator_applies_default_expected_files_for_dna_asp():
    """assay_specific_panels should default expected_files from asp_category when omitted."""
    payload = normalize_collection_document(
        "assay_specific_panels",
        {
            "asp_id": "assay_1",
            "assay_name": "assay_1",
            "asp_group": "hematology",
            "asp_family": "panel-dna",
            "asp_category": "dna",
            "display_name": "Assay 1",
        },
    )
    assert payload["expected_files"] == [
        "vcf_files",
        "cnv",
        "cnvprofile",
        "cov",
        "transloc",
        "biomarkers",
    ]


def test_collection_validator_rejects_cross_category_expected_files():
    """assay_specific_panels should reject file keys outside the assay category."""
    with pytest.raises(ValueError):
        normalize_collection_document(
            "assay_specific_panels",
            {
                "asp_id": "assay_rna",
                "assay_name": "assay_rna",
                "asp_group": "rna",
                "asp_family": "panel-rna",
                "asp_category": "rna",
                "display_name": "RNA Assay",
                "expected_files": ["fusion_files", "vcf_files"],
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
    payload["permissions"] = _load_reference_seed_list("permissions.seed.ndjson.gz")
    payload["roles"] = _load_reference_seed_list("roles.seed.ndjson.gz")
    payload["refseq_canonical"] = _load_reference_seed_list("refseq_canonical.seed.ndjson.gz")
    payload["hgnc_genes"] = _load_reference_seed_list("hgnc_genes.seed.ndjson.gz")
    payload["vep_metadata"] = _load_reference_seed_list("vep_metadata.seed.ndjson.gz")
    strict_ready = {
        "cnvs",
        "mane_select",
        "oncokb_genes",
        "permissions",
        "refseq_canonical",
        "roles",
        "samples",
        "vep_metadata",
    }
    for collection in strict_ready:
        docs = payload[collection]
        for doc in docs:
            validate_collection_document(collection, doc)
