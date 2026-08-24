"""Tests for core DB document contracts."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from api.config.database_versions import normalize_database_versions, require_sample_vep_version
from api.contracts.managed_resources import managed_resource_spec
from api.contracts.managed_ui_schemas import build_form_spec
from api.contracts.schemas.app_controls import AppControlsDoc
from api.contracts.schemas.assay import InsilicoGenelistsDoc
from api.contracts.schemas.dna import CnvsDoc, VariantsDoc
from api.contracts.schemas.governance import RolesDoc, UsersDoc
from api.contracts.schemas.registry import (
    normalize_collection_document,
    supported_collections,
    validate_collection_document,
)
from api.contracts.schemas.samples import SampleCaseControlDoc, SamplesDoc


def test_isgl_diagnosis_is_the_canonical_multi_subpanel_scope():
    """ISGL diagnosis accepts comma/newline tags without a duplicate subpanel field."""
    doc = InsilicoGenelistsDoc.model_validate(
        {
            "isgl_id": "solid_scope",
            "name": "Solid scope",
            "displayname": "Solid scope",
            "diagnosis": "endometrie, breast\ncolon, breast",
            "list_type": ["snv"],
            "asp_groups": ["solid"],
            "asp_ids": ["solid_gmsv3"],
        }
    )

    assert doc.diagnosis == ["endometrie", "breast", "colon"]
    assert "subpanel_id" not in doc.model_dump()


def _load_seed_list(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_reference_seed_list(filename: str) -> list[dict]:
    base = (
        Path("api/config/bootstrap/rbac")
        if filename.startswith(("permissions.", "roles."))
        else Path("api/config/bootstrap/reference")
    )
    path = base / filename
    if not path.exists() and filename.endswith(".gz"):
        path = base / filename[:-3]
    docs: list[dict] = []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                docs.append(json.loads(text))
    return docs


def test_variant_info_accepts_selected_csq_fields():
    """Variant documents retain only the selected transcript summary."""
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
            "selected_CSQ": {"Feature": "ENST1", "SYMBOL": "TP53"},
            "selected_CSQ_criteria": "ncbi_mane_plus_clinical",
        },
        "simple_id": "1_100_A_G",
        "simple_id_hash": hashlib.md5("1_100_A_G".encode("utf-8")).hexdigest(),
    }
    doc = VariantsDoc.model_validate(payload)
    assert doc.INFO.selected_CSQ is not None
    assert doc.INFO.selected_CSQ.SYMBOL == "TP53"
    assert doc.INFO.selected_CSQ_criteria == "ncbi_mane_plus_clinical"


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
            "selected_CSQ": {"Feature": "ENST1", "SYMBOL": "TP53"},
            "selected_CSQ_criteria": "ncbi_mane_plus_clinical",
        },
        "simple_id": "1_100_A_G",
        "simple_id_hash": hashlib.md5("1_100_A_G".encode("utf-8")).hexdigest(),
    }
    doc = VariantsDoc.model_validate(payload)
    assert doc.INFO.variant_callers == ["tnscope", "strelka"]
    assert doc.INFO.selected_CSQ.Feature == "ENST1"


def test_variant_consequence_terms_normalize_all_transcript_terms() -> None:
    payload = {
        "SAMPLE_ID": "S1",
        "CHROM": "1",
        "POS": 100,
        "REF": "A",
        "ALT": "G",
        "ID": ".",
        "INFO": {
            "selected_CSQ": {"Feature": "ENST1", "SYMBOL": "TP53"},
            "selected_CSQ_criteria": "first_available",
        },
        "consequence_terms": ["missense_variant&splice_region_variant", "missense_variant"],
        "simple_id": "1_100_A_G",
        "simple_id_hash": hashlib.md5("1_100_A_G".encode("utf-8")).hexdigest(),
    }

    doc = VariantsDoc.model_validate(payload)

    assert doc.consequence_terms == ["missense_variant", "splice_region_variant"]


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
    fixture = Path("demo_data/collections/all_collections_dummy/oncokb_actionable.json")
    payload = _load_seed_list(fixture)[0]
    validate_collection_document("oncokb_actionable", payload)


def test_collection_validator_accepts_public_oncokb_cancer_gene_shape():
    """Public OncoKB cancer-gene list records should validate as public markers."""
    validate_collection_document(
        "oncokb_cancer_genes_public",
        {
            "gene": "TP53",
            "source": "public.api.oncokb.org",
            "public_api": True,
            "therapeutic_data_included": False,
            "hgnc_id": "HGNC:11998",
            "previous_symbols": ["P53"],
            "alias_symbols": ["BCC7"],
            "entrez_gene_id": 7157,
            "gene_type": "TSG",
            "occurrence_count": 100,
            "oncokb_annotated": True,
            "sanger_cgc": True,
            "vogelstein": True,
            "foundation": True,
            "foundation_heme": True,
            "msk_impact": True,
            "msk_heme": True,
            "grch37_refseq": "NM_000546.5",
            "grch38_refseq": "NM_000546.6",
        },
    )


def test_collection_validator_accepts_nested_sample_shape():
    """samples collection should validate nested case/control/filter/comment/report blocks."""
    fixture = Path("demo_data/collections/all_collections_dummy/samples.json")
    payload = _load_seed_list(fixture)[0]
    validate_collection_document("samples", payload)


def test_cnvs_doc_normalizes_pipeline_callers_and_symbolic_ratio():
    doc = CnvsDoc.model_validate(
        {
            "SAMPLE_ID": "S1",
            "chr": "1",
            "start": 100,
            "end": 200,
            "size": 100,
            "ratio": "DEL",
            "genes": [{"gene": "TP53"}],
            "callers": "manta",
        }
    )

    assert doc.nprobes == 0
    assert doc.callers == ["manta"]
    assert doc.ratio == -1.0


def test_samples_doc_keeps_filters_unset_until_initialized():
    """SamplesDoc should leave filters unset until sample defaults are materialized elsewhere."""
    dna_doc = SamplesDoc.model_validate(
        {
            "name": "S1",
            "asp_id": "assay_1",
            "subpanel_id": "hem",
            "environment": "production",
            "case_id": "seed_case",
            "sample_no": 1,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "SomaticPanelPipeline",
            "pipeline_version": "1.0.0",
            "vcf_files": "x",
        }
    )
    assert dna_doc.filters is None
    assert dna_doc.ingest_status == "loading"
    assert isinstance(dna_doc.case, SampleCaseControlDoc)
    assert "filters" not in dna_doc.model_dump(exclude_none=True)

    rna_doc = SamplesDoc.model_validate(
        {
            "name": "S2",
            "asp_id": "fusion_assay",
            "subpanel_id": "rna",
            "environment": "production",
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


def test_samples_doc_accepts_only_persisted_ingest_states():
    payload = {
        "name": "S1",
        "asp_id": "assay_1",
        "subpanel_id": "base",
        "environment": "production",
        "case_id": "seed_case",
        "sample_no": 1,
        "sequencing_scope": "panel",
        "omics_layer": "dna",
        "pipeline": "SomaticPanelPipeline",
        "pipeline_version": "1.0.0",
        "files": {"vcf_files": {"path": "x"}},
        "ingest_status": "ready",
    }

    assert SamplesDoc.model_validate(payload).ingest_status == "ready"

    payload["ingest_status"] = "failed"
    with pytest.raises(ValueError, match="ingest_status"):
        SamplesDoc.model_validate(payload)


def test_samples_doc_omits_unknown_pipeline_version_placeholders():
    payload = {
        "name": "S1",
        "asp_id": "assay_1",
        "subpanel_id": "base",
        "environment": "production",
        "case_id": "seed_case",
        "sample_no": 1,
        "sequencing_scope": "panel",
        "omics_layer": "dna",
        "pipeline": "SomaticPanelPipeline",
        "pipeline_version": "not provided",
        "files": {"vcf_files": {"path": "x"}},
    }

    sample = SamplesDoc.model_validate(payload)

    assert sample.pipeline_version is None
    assert "pipeline_version" not in sample.model_dump(exclude_none=True)


def test_samples_doc_normalizes_one_sample_level_sex_value():
    payload = {
        "name": "S1",
        "asp_id": "assay_1",
        "subpanel_id": "base",
        "environment": "production",
        "case_id": "seed_case",
        "sample_no": 1,
        "sequencing_scope": "panel",
        "omics_layer": "dna",
        "sex": " Female ",
        "pipeline": "SomaticPanelPipeline",
        "files": {"vcf_files": {"path": "x"}},
    }

    sample = SamplesDoc.model_validate(payload)

    assert sample.sex == "female"
    assert "sex" not in sample.case.model_dump(exclude_none=True)

    payload["sex"] = "F"
    with pytest.raises(ValueError, match="sex"):
        SamplesDoc.model_validate(payload)


def test_sample_database_versions_use_only_canonical_nested_keys():
    """Sample VEP metadata belongs only in database_versions.vep."""
    assert normalize_database_versions({"vep": "v103", "clinvar": 202008, "cosmic": "null"}) == {
        "vep": "103",
        "clinvar": "202008",
    }

    with pytest.raises(ValueError, match="database_versions keys"):
        normalize_database_versions({"VEP": "103"})

    with pytest.raises(ValueError, match="database_versions.vep"):
        require_sample_vep_version({"database_versions": {}})

    payload = {
        "name": "S1",
        "assay": "assay_1",
        "subpanel": "hem",
        "profile": "production",
        "case_id": "seed_case",
        "sample_no": 1,
        "sequencing_scope": "panel",
        "omics_layer": "dna",
        "pipeline": "SomaticPanelPipeline",
        "pipeline_version": "1.0.0",
        "vcf_files": "x",
        "vep_version": "103",
    }
    with pytest.raises(ValueError, match="Retired sample fields"):
        SamplesDoc.model_validate(payload)


def test_platform_derives_read_technology_and_rejects_invalid_read_mode():
    """Platform capability is software-owned and cannot be contradicted in a sample."""
    payload = {
        "name": "S1",
        "asp_id": "assay_1",
        "subpanel_id": "base",
        "environment": "production",
        "case_id": "seed_case",
        "sample_no": 1,
        "sequencing_scope": "panel",
        "omics_layer": "dna",
        "platform": "illumina",
        "read_mode": "PE",
        "pipeline": "SomaticPanelPipeline",
        "pipeline_version": "1.0.0",
        "files": {"vcf_files": {"path": "x"}},
    }
    sample = SamplesDoc.model_validate(payload)
    assert sample.read_technology == "short_read"

    payload["platform"] = "iontorrent"
    with pytest.raises(ValueError, match="read_mode 'PE' is not supported"):
        SamplesDoc.model_validate(payload)


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
    fixture = Path("demo_data/collections/all_collections_dummy/panel_coverage.json")
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


def test_users_doc_validates_one_global_analysis_layout_preference():
    """User analysis layout is global and limited to the supported presentation modes."""
    payload = {
        "email": "tester@example.com",
        "username": "tester",
        "firstname": "Test",
        "lastname": "User",
        "fullname": "Test User",
        "job_title": "Scientist",
    }

    assert UsersDoc.model_validate(payload).ui_settings.analysis_layout == "classic"
    assert UsersDoc.model_validate(payload).ui_settings.sample_list_layout == "classic"
    assert UsersDoc.model_validate(payload).ui_settings.analysis_modern_view_tried is False
    assert UsersDoc.model_validate(payload).ui_settings.sample_list_modern_view_tried is False
    with pytest.raises(ValueError, match="analysis_layout must be one of"):
        UsersDoc.model_validate({**payload, "ui_settings": {"analysis_layout": "dna_tabs"}})
    with pytest.raises(ValueError, match="sample_list_layout must be one of"):
        UsersDoc.model_validate({**payload, "ui_settings": {"sample_list_layout": "combined"}})


def test_app_controls_doc_accepts_persisted_created_timestamp():
    """Persisted app controls should validate after Mongo adds created_on."""
    doc = AppControlsDoc.model_validate(
        {
            "control_id": "default",
            "celery": {"enabled": True},
            "retention": {"audit_events_days": 730, "notification_days": 180},
            "modules": {"dna_analysis_enabled": True},
            "created_on": "2026-07-17T16:02:06.074000Z",
            "updated_on": "2026-07-17T16:02:06.074000Z",
            "updated_by": "coyote3.admin",
        }
    )
    assert doc.created_on is not None
    assert doc.control_id == "default"


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
    assert form["fields"]["ui_settings"]["display_type"] == "user-settings"
    assert form["sections"]["user settings"] == ["ui_settings"]


def test_managed_role_form_exposes_runtime_color_picker():
    form = build_form_spec(managed_resource_spec("role"))

    assert form["fields"]["color"]["display_type"] == "color"
    assert form["fields"]["color"]["placeholder"] == "#4f46e5"


def test_role_color_normalizes_hex_and_preserves_legacy_names():
    base = {
        "role_id": "reviewer",
        "name": "reviewer",
        "label": "Reviewer",
        "level": 20,
    }

    assert RolesDoc.model_validate({**base, "color": " #DC2626 "}).color == "#dc2626"
    assert RolesDoc.model_validate({**base, "color": "Slate"}).color == "slate"
    with pytest.raises(ValueError, match="six-digit"):
        RolesDoc.model_validate({**base, "color": "#fff"})


def test_managed_clinical_forms_expose_system_metadata_read_only_after_create():
    """Clinical configuration provenance is visible but cannot be edited."""
    expected_metadata = {
        "version",
        "supersedes_id",
        "created_by",
        "created_on",
        "updated_by",
        "updated_on",
        "retired_by",
        "retired_on",
        "retired_reason",
    }

    for resource_key in ("asp", "aspc_dna", "aspc_rna", "isgl"):
        form = build_form_spec(managed_resource_spec(resource_key))
        metadata_fields = set(form["sections"]["system metadata"])
        assert expected_metadata <= metadata_fields
        for field_name in expected_metadata:
            field = form["fields"][field_name]
            assert field["readonly"] is True
            assert field["hidden_mode"] == ["create"]

    aspc_form = build_form_spec(managed_resource_spec("aspc_dna"))
    assert aspc_form["fields"]["platform"]["readonly"] is True
    assert {"aspc_id", "platform"} <= set(aspc_form["sections"]["configuration scope"])


def test_managed_isgl_form_uses_predefined_list_type_choices():
    """ISGL list types should be selected from fixed choices, not free text."""
    form = build_form_spec(managed_resource_spec("isgl"))
    assert form["fields"]["list_type"]["display_type"] == "checkbox-group"
    assert form["fields"]["list_type"]["options"] == [
        "snv",
        "cnv",
        "fusion",
        "expression",
        "pgx",
        "adhoc_snv",
        "adhoc_cnv",
        "adhoc_fusion",
        "adhoc_expression",
        "adhoc_pgx",
    ]
    assert form["fields"]["list_type"]["conditional_options"]["falsy"] == [
        "snv",
        "cnv",
        "fusion",
        "expression",
        "pgx",
    ]
    assert form["fields"]["list_type"]["conditional_options"]["truthy"] == [
        "adhoc_snv",
        "adhoc_cnv",
        "adhoc_fusion",
        "adhoc_expression",
        "adhoc_pgx",
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
        "hgnc_genes",
    ):
        assert required in names


def test_collection_validator_rejects_invalid_aspc_identifier():
    """asp_configs should use simple generated identifiers, not compound punctuation keys."""
    with pytest.raises(ValueError):
        validate_collection_document(
            "asp_configs",
            {
                "aspc_id": "assay_1:production",
                "asp_id": "assay_1",
                "subpanel_id": "base",
                "environment": "production",
                "asp_group": "hematology",
            },
        )


def test_collection_validator_rejects_unknown_asp_group():
    """ASP and ASPC docs should only allow known assay-group values."""
    with pytest.raises(ValueError):
        normalize_collection_document(
            "assay_specific_panels",
            {
                "asp_id": "assay_unknown",
                "assay_name": "assay_unknown",
                "asp_group": "custom-group",
                "asp_family": "panel-dna",
                "asp_category": "dna",
                "display_name": "Assay Unknown",
            },
        )


def test_collection_validator_rejects_unknown_platform():
    """ASP docs should only allow known sequencing platform values."""
    with pytest.raises(ValueError):
        normalize_collection_document(
            "assay_specific_panels",
            {
                "asp_id": "assay_bad_platform",
                "assay_name": "assay_bad_platform",
                "asp_group": "hematology",
                "asp_family": "panel-dna",
                "asp_category": "dna",
                "display_name": "Assay Bad Platform",
                "platform": "bgiseq",
            },
        )


def test_collection_validator_requires_canonical_aspc_analysis_types():
    """asp_configs should accept canonical analysis-type values."""
    payload = normalize_collection_document(
        "asp_configs",
        {
            "aspc_id": "assay_1_base_development",
            "asp_id": "assay_1",
            "subpanel_id": "base",
            "environment": "development",
            "asp_group": "hematology",
            "asp_category": "dna",
            "analysis_types": ["SNV", "TMB", "PGX", "CNV_PROFILE", "COVERAGE"],
            "display_name": "Assay 1 Dev",
            "analysis_intents": ["somatic"],
            "filters": {
                "somatic": {
                    "snv": {"vep_consequences": ["missense"]},
                    "cnv": {"cnveffects": ["gain", "loss"]},
                    "coverage": {"warn_cov": 500, "error_cov": 100},
                }
            },
            "reporting": {
                "report_sections": ["TMB", "CNV_PROFILE"],
                "report_header": "Header",
                "report_method": "Method",
                "report_description": "Description",
                "general_report_summary": "Summary",
                "plots_path": "/tmp",
                "report_folder": "reports",
            },
        },
    )

    assert payload["analysis_types"] == ["SNV", "TMB", "PGX", "CNV_PROFILE", "COVERAGE"]
    assert payload["reporting"]["report_sections"] == ["TMB", "CNV_PROFILE"]
    assert "analysis" not in payload["reporting"]


def test_collection_validator_requires_translocation_filter_scope() -> None:
    """A translocation-enabled ASPC must define its independent gene-scope block."""
    with pytest.raises(
        ValueError,
        match=r"analysis_types includes TRANSLOCATION but filters\.somatic\.translocation is missing",
    ):
        normalize_collection_document(
            "asp_configs",
            {
                "aspc_id": "assay_1_base_development",
                "asp_id": "assay_1",
                "subpanel_id": "base",
                "environment": "development",
                "asp_group": "hematology",
                "asp_category": "dna",
                "analysis_types": ["SNV", "TRANSLOCATION"],
                "display_name": "Assay 1 Dev",
                "analysis_intents": ["somatic"],
                "filters": {"somatic": {"snv": {"vep_consequences": ["missense"]}}},
                "reporting": {
                    "report_sections": ["SNV"],
                    "report_header": "Header",
                    "report_method": "Method",
                    "report_description": "Description",
                    "general_report_summary": "Summary",
                    "plots_path": "/tmp",
                    "report_folder": "reports",
                },
            },
        )


def test_collection_validator_normalizes_user_asp_groups_to_known_values():
    """User ASP-group scope should use the fixed assay-group vocabulary."""
    payload = normalize_collection_document(
        "users",
        {
            "email": "admin@your-center.org",
            "username": "admin.center",
            "firstname": "Admin",
            "lastname": "Center",
            "fullname": "Admin Center",
            "job_title": "Administrator",
            "roles": ["admin"],
            "environments": ["production"],
            "asp_groups": [" Hematology ", "solid"],
        },
    )

    assert payload["asp_groups"] == ["hematology", "solid"]


def test_collection_validator_rejects_unknown_permission_category():
    """Permission policy category should use the fixed category vocabulary."""
    with pytest.raises(ValueError):
        normalize_collection_document(
            "permissions",
            {
                "permission_id": "sample:inspect",
                "label": "Inspect sample",
                "category": "Custom Category",
                "tags": [],
            },
        )


def test_collection_validator_applies_default_expected_files_for_dna_asp():
    """assay_specific_panels should default expected_files from asp_category when omitted."""
    payload = normalize_collection_document(
        "assay_specific_panels",
        {
            "asp_id": "assay_1",
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
        "pgx",
    ]
    assert payload["required_files"] == []


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


def test_collection_validator_rejects_required_files_outside_expected_files():
    """assay_specific_panels should keep required_files as a subset of expected_files."""
    with pytest.raises(ValueError):
        normalize_collection_document(
            "assay_specific_panels",
            {
                "asp_id": "assay_dna",
                "assay_name": "assay_dna",
                "asp_group": "hematology",
                "asp_family": "panel-dna",
                "asp_category": "dna",
                "display_name": "DNA Assay",
                "expected_files": ["vcf_files", "cov"],
                "required_files": ["transloc"],
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
    fixture_dir = Path("demo_data/collections/all_collections_dummy")
    payload = {
        file.stem: json.loads(file.read_text(encoding="utf-8"))
        for file in sorted(fixture_dir.glob("*.json"))
    }
    payload["permissions"] = _load_reference_seed_list("permissions.seed.ndjson.gz")
    payload["roles"] = _load_reference_seed_list("roles.seed.ndjson.gz")
    payload["hgnc_genes"] = _load_reference_seed_list("hgnc_genes.seed.ndjson.gz")
    payload["vep_metadata"] = _load_reference_seed_list("vep_metadata.seed.ndjson.gz")
    strict_ready = {
        "cnvs",
        "mane_select",
        "oncokb_genes",
        "permissions",
        "roles",
        "samples",
        "vep_metadata",
    }
    for collection in strict_ready:
        docs = payload[collection]
        for doc in docs:
            validate_collection_document(collection, doc)
