"""Behavior tests for DNA API route helpers and endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routes import dna
from tests.api.fixtures import mock_collections as fx


def test_mutation_payload_shape():
    payload = dna._mutation_payload("S1", "variant", "V1", "flag")
    assert payload["status"] == "ok"
    assert payload["sample_id"] == "S1"
    assert payload["resource"] == "variant"
    assert payload["resource_id"] == "V1"
    assert payload["action"] == "flag"


def test_load_cnvs_for_sample_uses_collection_shaped_docs(monkeypatch):
    sample = fx.sample_doc()
    sample_filters = sample["filters"]
    cnv_rows = [fx.cnv_doc()]

    monkeypatch.setattr(dna, "build_cnv_query", lambda sample_id, filters: {"sample_id": sample_id, **filters})
    monkeypatch.setattr(dna.store.cnv_handler, "get_sample_cnvs", lambda query: cnv_rows)
    monkeypatch.setattr(dna, "create_cnveffectlist", lambda cnv_effects: [])
    monkeypatch.setattr(dna, "cnv_organizegenes", lambda cnvs: cnvs)

    rows = dna._load_cnvs_for_sample(sample, sample_filters, ["ERBB2"])
    assert rows == cnv_rows


def test_list_dna_biomarkers_success(monkeypatch):
    sample = fx.sample_doc()
    biomarkers = [{"_id": "b1", "name": "TMB", "value": "High"}]

    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(dna.store.biomarker_handler, "get_sample_biomarkers", lambda sample_id: biomarkers)
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.list_dna_biomarkers("S1", user=fx.api_user())
    assert payload["meta"]["count"] == 1
    assert payload["biomarkers"][0]["name"] == "TMB"


def test_show_dna_variant_not_found_raises_404(monkeypatch):
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(dna.store.variant_handler, "get_variant", lambda var_id: None)

    with pytest.raises(HTTPException) as exc:
        dna.show_dna_variant("S1", "V404", user=fx.api_user())

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Variant not found"


def test_list_dna_variants_does_not_require_report_path(monkeypatch):
    sample = fx.sample_doc()
    sample.setdefault("filters", {}).setdefault("max_freq", 1.0)
    sample["filters"].setdefault("min_freq", 0.0)
    sample["filters"].setdefault("max_control_freq", 1.0)
    sample["filters"].setdefault("min_depth", 0)
    sample["filters"].setdefault("min_alt_reads", 0)
    sample["filters"].setdefault("max_popfreq", 1.0)
    sample["filters"].setdefault("vep_consequences", [])
    sample["filters"].setdefault("genelists", [])
    sample.setdefault("subpanel", "")

    assay_config = {
        "asp_group": "tumwgs",
        "analysis_types": [],
        "schema_name": "schema-dna",
        "reporting": {},  # intentionally missing report_path
    }

    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(dna, "_get_formatted_assay_config", lambda _sample: assay_config)
    monkeypatch.setattr(dna.util.common, "merge_sample_settings_with_assay_config", lambda s, a: s)
    monkeypatch.setattr(dna.store.asp_handler, "get_asp", lambda asp_name: {"asp_name": asp_name})
    monkeypatch.setattr(dna.store.isgl_handler, "get_isgl_by_ids", lambda ids: {})
    monkeypatch.setattr(dna.util.common, "get_sample_effective_genes", lambda s, a, g: ([], []))
    monkeypatch.setattr(dna, "get_filter_conseq_terms", lambda values: [])
    monkeypatch.setattr(dna, "build_query", lambda assay_group, params: {"assay_group": assay_group, **params})
    monkeypatch.setattr(dna.store.variant_handler, "get_case_variants", lambda query: [])
    monkeypatch.setattr(dna.store.blacklist_handler, "add_blacklist_data", lambda variants, assay_group: variants)
    monkeypatch.setattr(dna, "add_global_annotations", lambda variants, assay_group, subpanel: (variants, []))
    monkeypatch.setattr(dna, "hotspot_variant", lambda variants: variants)
    monkeypatch.setattr(dna.util.common, "get_case_and_control_sample_ids", lambda s: {"case": "C1"})
    monkeypatch.setattr(dna.store.bam_service_handler, "get_bams", lambda sample_ids: {})
    monkeypatch.setattr(dna.store.vep_meta_handler, "get_variant_class_translations", lambda vep: {})
    monkeypatch.setattr(dna.store.vep_meta_handler, "get_conseq_translations", lambda vep: {})
    monkeypatch.setattr(dna.store.sample_handler, "hidden_sample_comments", lambda sample_oid: False)
    monkeypatch.setattr(dna.store.isgl_handler, "get_isgl_by_asp", lambda assay, is_active=True: [])
    monkeypatch.setattr(dna.util.common, "get_assay_genelist_names", lambda docs: [])
    monkeypatch.setattr(dna.store.schema_handler, "get_schema", lambda schema_name: {})
    monkeypatch.setattr(dna, "generate_summary_text", lambda *args, **kwargs: "")
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    req = SimpleNamespace(url=SimpleNamespace(path="/api/v1/dna/samples/S1/variants"))
    payload = dna.list_dna_variants(req, "S1", user=fx.api_user())

    assert payload["sample"]["name"] == sample["name"]
    assert payload["meta"]["count"] == 0


def test_classify_variant_mutation_calls_insert(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(dna.util.common, "get_tier_classification", lambda form_data: 3)
    monkeypatch.setattr(dna, "get_variant_nomenclature", lambda form_data: ("p", "TP53 p.R175H"))
    monkeypatch.setattr(
        dna.store.annotation_handler,
        "insert_classified_variant",
        lambda variant, nomenclature, class_num, form_data, **kwargs: captured.update(
            {
                "variant": variant,
                "nomenclature": nomenclature,
                "class_num": class_num,
                "author": kwargs.get("author"),
            }
        ),
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.classify_variant_mutation(
        "S1",
        payload={"id": "V1", "form_data": {"tier3": "on"}},
        user=fx.api_user(),
    )

    assert payload["status"] == "ok"
    assert captured["variant"] == "TP53 p.R175H"
    assert captured["class_num"] == 3
