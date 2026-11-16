"""Unit tests for DNA payload builders."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from api_test_support import mock_collections as fx
from coyote.application.dna import payloads
from coyote.domain.exceptions import AppError
from coyote_api.interfaces.http.v1.clinical.common.analysis_query import analysis_query_from_request


@pytest.mark.parametrize("mode", ["shared", "independent"])
def test_list_variants_payload_sorts_main_variant_table_by_case_af_desc(mode, monkeypatch) -> None:
    """The main SNV/INDEL table should arrive pre-sorted by case AF descending."""
    sample = fx.sample_doc()
    sample["analysis_intents"] = ["somatic", "germline"]
    sample["filters"]["somatic"]["snv"]["exclude_flags"] = ["WARN_NOVAR"]
    queries = []
    assay_config = {
        **fx.assay_config_doc(asp_group="tumwgs"),
        "asp_group": "tumwgs",
        "analysis_types": ["SNV"],
        "snv_filter_mode": mode,
        "reporting": {},
    }
    evaluations = []
    germline_loads = []

    def evaluate(**kwargs):
        evaluations.append(kwargs)
        return None

    def load_germline(**kwargs):
        germline_loads.append(kwargs)
        return [{"symbol": "BRCA1", "classification": {"class": 2}}]

    monkeypatch.setattr(payloads, "load_report_snv_findings", load_germline)
    variants = [
        {"_id": "low", "GT": [{"type": "case", "AF": 0.12}]},
        {"_id": "high", "GT": [{"type": "case", "AF": 0.89}]},
        {"_id": "mid", "GT": [{"type": "case", "AF": 0.34}]},
    ]

    service = SimpleNamespace(
        clinical_rule_service=SimpleNamespace(evaluate=evaluate),
        annotation_repository=object(),
        query_rule_service=None,
        assay_panel_repository=SimpleNamespace(get_asp=lambda asp_name: {"asp_name": asp_name}),
        gene_list_repository=SimpleNamespace(
            get_isgl_by_ids=lambda ids: {},
            get_isgl_by_asp=lambda assay, is_active=True: [],
        ),
        variant_repository=SimpleNamespace(
            get_case_variants=lambda query: queries.append(query) or variants,
            hydrate_finding_comments_many=lambda findings: findings,
        ),
        blacklist_repository=SimpleNamespace(
            add_blacklist_data=lambda rows, assay_group, *, asp_id: rows
        ),
        bam_record_repository=SimpleNamespace(get_bams=lambda sample_ids: {}),
        vep_metadata_repository=SimpleNamespace(
            get_variant_class_translations=lambda vep: {},
            get_conseq_translations=lambda vep: {},
        ),
        sample_repository=SimpleNamespace(hidden_sample_comments=lambda sample_oid: False),
        oncokb_repository=SimpleNamespace(get_oncokb_action_gene=lambda symbol: None),
    )

    payload = payloads.list_variants_payload(
        service=service,
        query=analysis_query_from_request(
            SimpleNamespace(
                query_params={}, url=SimpleNamespace(path="/api/v1/samples/S1/small-variants")
            )
        ),
        sample=sample,
        add_global_annotations_fn=lambda rows, assay_group, diagnosis, **kwargs: (rows, []),
        build_query_fn=lambda assay_group, params, intent="somatic", policy=None: {
            "assay_group": assay_group,
            "intent": intent,
            **params,
        },
        get_filter_conseq_terms_fn=lambda values: [],
        assay_config_getter=lambda _sample: assay_config,
        include_report_context=True,
    )

    assert [variant["_id"] for variant in payload["variants"]] == ["high", "mid", "low"]
    assert queries[0]["exclude_flags"] == ["WARN_NOVAR"]
    assert [variant["_id"] for variant in payload["display_sections_data"]["snvs"]] == [
        "high",
        "mid",
        "low",
    ]
    if mode == "independent":
        assert germline_loads[0]["intent"] == "germline"
        germline = evaluations[0]["intent_contexts"]["germline"]
        assert germline.aggregates.snv_count == 1
        assert germline.findings[0].gene == "BRCA1"
        assert germline.sample.analysis_intent == "germline"
    else:
        assert germline_loads == []
        assert "intent_contexts" not in evaluations[0]


def test_paginated_small_variant_list_only_enriches_the_current_page() -> None:
    """A normal table page does not run classification lookups for every finding."""
    sample = fx.sample_doc()
    assay_config = {
        **fx.assay_config_doc(asp_group="tumwgs"),
        "analysis_types": [],
        "reporting": {},
    }
    variants = [
        {"_id": str(index), "GT": [{"type": "case", "AF": index / 100}]} for index in range(100)
    ]
    enriched_counts: list[int] = []
    service = SimpleNamespace(
        query_rule_service=None,
        assay_panel_repository=SimpleNamespace(get_asp=lambda asp_name: {"asp_name": asp_name}),
        gene_list_repository=SimpleNamespace(
            get_isgl_by_ids=lambda ids: {}, get_isgl_by_asp=lambda assay, is_active=True: []
        ),
        variant_repository=SimpleNamespace(
            get_case_variants=lambda query: variants,
            hydrate_finding_comments_many=lambda findings: findings,
        ),
        blacklist_repository=SimpleNamespace(
            add_blacklist_data=lambda rows, assay_group, *, asp_id: rows
        ),
        bam_record_repository=SimpleNamespace(get_bams=lambda sample_ids: {}),
        vep_metadata_repository=SimpleNamespace(
            get_variant_class_translations=lambda vep: {}, get_conseq_translations=lambda vep: {}
        ),
        sample_repository=SimpleNamespace(hidden_sample_comments=lambda sample_oid: False),
        oncokb_repository=SimpleNamespace(get_oncokb_action_gene=lambda symbol: None),
    )

    payload = payloads.list_variants_payload(
        service=service,
        query=analysis_query_from_request(
            SimpleNamespace(
                query_params={"page": "1", "per_page": "50"},
                url=SimpleNamespace(path="/api/v1/samples/S1/small-variants"),
            )
        ),
        sample=sample,
        add_global_annotations_fn=lambda rows, *_args, **_kwargs: (
            enriched_counts.append(len(rows)) or rows,
            [],
        ),
        build_query_fn=lambda assay_group, params, intent="somatic", policy=None: {},
        get_filter_conseq_terms_fn=lambda values: [],
        assay_config_getter=lambda _sample: assay_config,
    )

    assert len(payload["variants"]) == 50
    assert enriched_counts == [50]
    assert payload["meta"]["tiered_count"] is None


def test_list_variants_payload_keeps_tmb_and_pgx_independent() -> None:
    """TMB is selected independently and PGX does not expose other measurements."""
    sample = fx.sample_doc()
    assay_config = {
        **fx.assay_config_doc(asp_group="panel"),
        "asp_group": "panel",
        "analysis_types": ["SNV", "TMB", "PGX"],
        "reporting": {},
    }

    service = SimpleNamespace(
        query_rule_service=None,
        assay_panel_repository=SimpleNamespace(get_asp=lambda asp_name: {"asp_name": asp_name}),
        gene_list_repository=SimpleNamespace(
            get_isgl_by_ids=lambda ids: {},
            get_isgl_by_asp=lambda assay, is_active=True: [],
        ),
        variant_repository=SimpleNamespace(
            get_case_variants=lambda query: [],
            hydrate_finding_comments_many=lambda findings: findings,
        ),
        blacklist_repository=SimpleNamespace(
            add_blacklist_data=lambda rows, assay_group, *, asp_id: rows
        ),
        bam_record_repository=SimpleNamespace(get_bams=lambda sample_ids: {}),
        vep_metadata_repository=SimpleNamespace(
            get_variant_class_translations=lambda vep: {},
            get_conseq_translations=lambda vep: {},
        ),
        sample_repository=SimpleNamespace(hidden_sample_comments=lambda sample_oid: False),
        oncokb_repository=SimpleNamespace(get_oncokb_action_gene=lambda symbol: None),
        biomarker_repository=SimpleNamespace(
            get_sample_biomarkers=lambda sample_id: [
                {"name": "TMB", "TMB": {"value": 12.4, "unit": "mut/Mb"}, "HRD": {"sum": 42}}
            ]
        ),
        load_cnvs_for_sample=lambda **kwargs: [],
        translocation_repository=SimpleNamespace(get_sample_translocations=lambda query: []),
    )

    payload = payloads.list_variants_payload(
        service=service,
        query=analysis_query_from_request(
            SimpleNamespace(
                query_params={}, url=SimpleNamespace(path="/api/v1/samples/S1/small-variants")
            )
        ),
        sample=sample,
        add_global_annotations_fn=lambda rows, assay_group, diagnosis, **kwargs: (rows, []),
        build_query_fn=lambda assay_group, params, intent="somatic", policy=None: {
            "assay_group": assay_group,
            "intent": intent,
            **params,
        },
        get_filter_conseq_terms_fn=lambda values: [],
        assay_config_getter=lambda _sample: assay_config,
    )

    assert payload["analysis_sections"] == ["SNV", "TMB", "PGX"]
    assert "HRD" not in payload["display_sections_data"]["biomarkers"][0]
    assert payload["display_sections_data"]["biomarkers"][0]["name"] == "TMB"


def test_list_variants_payload_rejects_unconfigured_analysis_intent() -> None:
    """A direct germline request must be a typed setup error, never a 500."""
    sample = fx.sample_doc()
    sample["analysis_intents"] = ["somatic"]

    with pytest.raises(AppError) as exc:
        payloads.list_variants_payload(
            service=SimpleNamespace(),
            query=analysis_query_from_request(
                SimpleNamespace(
                    query_params={"intent": "germline"},
                    url=SimpleNamespace(path="/api/v1/samples/S1/small-variants"),
                )
            ),
            sample=sample,
            add_global_annotations_fn=lambda *args: ([], []),
            build_query_fn=lambda *args, **kwargs: {},
            get_filter_conseq_terms_fn=lambda *args: [],
            assay_config_getter=lambda _sample: {"analysis_types": ["SNV"]},
        )

    assert exc.value.status_code == 422
    assert exc.value.message == "Small-variant analysis intent is unavailable for this sample"
