"""Tests for DNA/RNA workflow service facades."""

from __future__ import annotations

import logging
from copy import deepcopy
from types import SimpleNamespace

import pytest
from coyote.application.common.release_resources import capture_assay_resource, capture_gene_lists
from coyote.application.reporting import dna_workflow, rna_workflow


def _release(assay: str, group: str, *, rna: bool = False) -> dict:
    """Supply pinned synthetic resources to report workflows."""
    panel = {
        "asp_id": assay,
        "asp_group": group,
        "version": 1,
        "asp_category": "rna" if rna else "dna",
        "asp_family": "panel-rna" if rna else "panel-dna",
        "covered_genes": ["TP53", "EGFR", "EML4", "ALK"],
    }
    return {
        "asp_id": assay,
        "asp_group": group,
        "assay_resource_release": capture_assay_resource(panel),
        "gene_list_release": capture_gene_lists(
            []
            if rna
            else [
                {
                    "isgl_id": "CNV_GL",
                    "version": 1,
                    "genes": ["TP53"],
                    "list_type": ["cnv"],
                    "is_active": True,
                }
            ]
        ),
        "aspc_resolution": {
            "context": {
                "assay_id": assay,
                "group_id": group,
                "environment": "testing",
                "diagnosis_id": "base",
            }
        },
    }


def _rna_workflow(
    *,
    sample_repository=None,
    gene_list_repository=None,
    rna_expression_repository=None,
    rna_classification_repository=None,
    rna_quality_repository=None,
    fusion_repository=None,
    annotation_repository=None,
    assay_panel_repository=None,
    reported_variant_repository=None,
    report_repository=None,
) -> rna_workflow.RNAWorkflowService:
    stub = SimpleNamespace()
    return rna_workflow.RNAWorkflowService(
        sample_repository=sample_repository or stub,
        diagnosis_repository=SimpleNamespace(
            get_current=lambda *args: {"display_name": "Synthetic diagnosis"}
        ),
        gene_list_repository=gene_list_repository or stub,
        rna_expression_repository=rna_expression_repository or stub,
        rna_classification_repository=rna_classification_repository or stub,
        rna_quality_repository=rna_quality_repository or stub,
        fusion_repository=fusion_repository or stub,
        annotation_repository=annotation_repository or stub,
        assay_panel_repository=assay_panel_repository or stub,
        reported_variant_repository=reported_variant_repository or stub,
        report_repository=report_repository or stub,
        clinical_rule_service=None,
    )


def test_dna_clinical_rule_only_payload_skips_print_report_work(monkeypatch):
    def unexpected(*_args, **_kwargs):
        raise AssertionError("display-only report work must not run during rule testing")

    template_name, context, snapshot_rows = dna_workflow.DnaReportBuilder(
        plot_reader=unexpected,
        sample={
            "_id": "s1",
            "name": "S1",
            "asp_id": "assay_1",
            "diagnosis_id": "base",
            "database_versions": {"vep": "110"},
            "filters": {"somatic": {"snv": {"snvlists": [], "vep_consequences": []}}},
        },
        assay_config={
            **_release("assay_1", "hematology"),
            "asp_group": "hematology",
            "filters": {"somatic": {"snv": {"snvlists": [], "vep_consequences": []}}},
            "reporting": {"report_sections": ["SNV", "CNV_PROFILE"]},
        },
        variant_repository=SimpleNamespace(
            get_case_variants=lambda query: [], hydrate_finding_comments_many=unexpected
        ),
        blacklist_repository=SimpleNamespace(
            add_blacklist_data=lambda rows, group, *, asp_id: rows
        ),
        sample_repository=SimpleNamespace(get_latest_sample_comment=unexpected),
        diagnosis_repository=SimpleNamespace(
            get_current=lambda *args: {"display_name": "Synthetic diagnosis"}
        ),
        copy_number_variant_repository=SimpleNamespace(),
        biomarker_repository=SimpleNamespace(),
        translocation_repository=SimpleNamespace(),
        vep_metadata_repository=SimpleNamespace(
            get_consequence_group_map=lambda version: {}, get_variant_class_translations=unexpected
        ),
        annotation_repository=SimpleNamespace(),
        clinical_rule_service=SimpleNamespace(
            evaluate_document=lambda **kwargs: SimpleNamespace(
                model_dump=lambda **options: {"sections": {}, "trace": []}
            )
        ),
        clinical_rule_override=SimpleNamespace(),
        clinical_rule_only=True,
    ).build()

    assert template_name == ""
    assert context["clinical_rule_evaluation"] == {"sections": {}, "trace": []}
    assert snapshot_rows == []


def test_rna_clinical_rule_only_payload_skips_print_report_work():
    def unexpected(*_args, **_kwargs):
        raise AssertionError("display-only report work must not run during rule testing")

    workflow = _rna_workflow(
        sample_repository=SimpleNamespace(get_latest_sample_comment=unexpected),
        gene_list_repository=SimpleNamespace(get_isgl_by_ids=lambda ids: {}),
        fusion_repository=SimpleNamespace(
            get_sample_fusions=lambda query: [],
            hydrate_finding_comments_many=unexpected,
        ),
        assay_panel_repository=SimpleNamespace(get_asp=lambda asp_id: {}),
    )
    workflow.clinical_rule_service = SimpleNamespace(
        evaluate_document=lambda **kwargs: SimpleNamespace(
            model_dump=lambda **options: {"sections": {}, "trace": []}
        )
    )

    template_name, context, snapshot_rows = workflow.build_report_payload(
        sample={"_id": "s1", "name": "S1", "asp_id": "rna_assay"},
        assay_config={
            **_release("rna_assay", "rna", rna=True),
            "reporting": {"report_sections": ["FUSION"]},
        },
        save=0,
        include_snapshot=False,
        clinical_rule_override=SimpleNamespace(),
        clinical_rule_only=True,
    )

    assert template_name == ""
    assert context["clinical_rule_evaluation"] == {"sections": {}, "trace": []}
    assert snapshot_rows == []


def test_rna_workflow_merge_and_normalize_filters(monkeypatch):
    """RNA workflow merges defaults and validates normalized sample filters."""
    calls = {}

    monkeypatch.setattr(
        rna_workflow,
        "validate_rna_filter_inputs",
        lambda logger, sample_name, filters: calls.setdefault(
            "validate", (logger, sample_name, filters)
        ),
    )

    merged, normalized = rna_workflow.RNAWorkflowService.merge_and_normalize_sample_filters(
        {"name": "S1"},
        {"assay_name": "RNA"},
        "S1",
        logger="LOG",
    )
    assert merged["name"] == "S1"
    assert normalized == {}
    assert calls["validate"][1] == "S1"


@pytest.mark.parametrize("filters", [None, {}, {"somatic": {}}, {"somatic": {"fusion": None}}])
def test_rna_workflow_fills_missing_fusion_profile_from_pinned_defaults(filters):
    """An empty saved RNA profile must not discard the applied read thresholds."""
    sample = {"name": "SYNTHETIC", "asp_category": "rna", "filters": filters}
    before = deepcopy(sample)
    config = {
        "filters": {"somatic": {"fusion": {"min_spanning_reads": 7, "min_spanning_pairs": 3}}}
    }
    merged, section = rna_workflow.RNAWorkflowService.merge_and_normalize_sample_filters(
        sample, config, "sample", logging.getLogger(__name__)
    )
    assert section["min_spanning_reads"] == 7
    assert section["min_spanning_pairs"] == 3
    assert merged["filters"]["somatic"]["fusion"]["min_spanning_reads"] == 7
    assert sample == before


def test_rna_workflow_retains_explicit_zero_and_empty_filter_selections():
    """Existing sample selections override ASPC defaults, including explicit zero."""
    sample = {
        "name": "SYNTHETIC",
        "asp_category": "rna",
        "filters": {"somatic": {"fusion": {"min_spanning_reads": 0, "fusionlists": []}}},
    }
    config = {
        "filters": {"somatic": {"fusion": {"min_spanning_reads": 7, "fusionlists": ["curated"]}}}
    }
    _merged, section = rna_workflow.RNAWorkflowService.merge_and_normalize_sample_filters(
        sample, config, "sample", logging.getLogger(__name__)
    )
    assert section["min_spanning_reads"] == 0
    assert section["fusionlists"] == []


def test_rna_workflow_build_context_and_query(monkeypatch):
    """RNA workflow builds filter context and fusion query payload."""
    calls = {}
    workflow = _rna_workflow(
        gene_list_repository=SimpleNamespace(
            get_isgl_by_ids=lambda _ids: {"L1": {"genes": ["TP53"]}}
        )
    )

    monkeypatch.setattr(rna_workflow, "create_fusioneffectlist", lambda values: values)
    monkeypatch.setattr(rna_workflow, "create_fusioncallers", lambda values: values)

    def _build_query(assay_group, settings, policy=None):
        calls["query"] = (assay_group, settings)
        return {"ok": True}

    monkeypatch.setattr(rna_workflow, "build_fusion_query", _build_query)

    context = workflow.compute_filter_context(
        {
            "name": "S1",
            "asp_category": "rna",
            "filters": {"somatic": {"fusion": {"fusionlists": ["L1"]}}},
        },
        {"fusion_effects": ["in-frame"], "fusion_callers": ["arriba"], "fusionlists": ["L1"]},
        {"asp_id": "RNA", "covered_genes": ["TP53"]},
        {"L1": {"genes": ["TP53"], "list_type": ["fusion"], "is_active": True}},
    )
    query = rna_workflow.RNAWorkflowService.build_fusion_list_query(
        "hema",
        "sample-1",
        {"min_spanning_reads": 2, "min_spanning_pairs": 3},
        context,
        sample={"asp_id": "rna_panel", "diagnosis_id": "base"},
    )

    assert context["fusion_effect_form_keys"] == ["inframe"]
    assert context["filter_genes"] == ["TP53"]
    assert query == {"ok": True}
    assert calls["query"][0] == "hema"
    assert calls["query"][1]["id"] == "sample-1"
    assert calls["query"][1]["asp_id"] == "rna_panel"


def test_rna_snapshot_rows_and_report_payload(monkeypatch):
    """RNA workflow builds snapshot rows and report payload."""
    fusion_doc = {
        "_id": "f1",
        "gene1": "KMT2A",
        "gene2": "AFF1",
        "interesting": False,
        "calls": [
            {
                "selected": 1,
                "breakpoint1": "chr11:1",
                "breakpoint2": "chr4:2",
                "effect": "in-frame",
                "spanpairs": 8,
                "spanreads": 13,
                "longestanchor": 42,
                "caller": "fusioncatcher",
            }
        ],
        "classification": {"class": 2, "_id": "ann1"},
        "global_annotations": [{"text": "Reviewed fusion", "time_created": "2026-01-01"}],
    }
    tier_four_interesting_fusion = {
        **fusion_doc,
        "_id": "f2",
        "gene1": "BCR",
        "gene2": "ABL1",
        "interesting": True,
        "classification": {"class": 4, "_id": "ann2"},
    }
    fusion_repository = SimpleNamespace(
        get_sample_fusions=lambda _query: [
            dict(fusion_doc),
            dict(tier_four_interesting_fusion),
        ],
        hydrate_finding_comments_many=lambda rows: rows,
    )

    monkeypatch.setattr(rna_workflow, "utc_now", lambda: "NOW")
    monkeypatch.setattr(
        rna_workflow,
        "persist_shared_report_and_snapshot",
        lambda **kwargs: kwargs["report_id"],
    )

    def scoped_annotations(fusion, group, diagnosis, *, sample_context):
        assert sample_context["assay_id"] == "fusion"
        assert group == "hema"
        assert diagnosis == "selected-panel"
        return [], fusion["classification"], [], {group: {"text": "a"}}

    workflow = _rna_workflow(
        fusion_repository=fusion_repository,
        annotation_repository=SimpleNamespace(
            get_global_annotations=scoped_annotations,
        ),
        gene_list_repository=SimpleNamespace(get_isgl_by_ids=lambda _ids: {}),
        assay_panel_repository=SimpleNamespace(get_asp=lambda _asp: {}),
        sample_repository=SimpleNamespace(get_latest_sample_comment=lambda _sample_id: None),
        reported_variant_repository=SimpleNamespace(),
    )
    rows = workflow._build_snapshot_rows([fusion_doc])
    assert rows[0]["simple_id"] == "KMT2A::AFF1::chr11:1::chr4:2"
    assert rows[0]["created_on"] == "NOW"
    assert rows[0]["fusion"] == "KMT2A::AFF1"
    assert rows[0]["effect"] == "in-frame"
    assert rows[0]["spanning_pairs"] == 8
    assert rows[0]["spanning_reads"] == 13
    assert rows[0]["classification"] == 2
    assert rows[0]["analysis_type"] == "FUSION"
    assert rows[0]["text"] == "Reviewed fusion"

    template, context, snapshot_rows = workflow.build_report_payload(
        {
            "_id": "S1",
            "name": "S1",
            "asp_id": "fusion",
            "diagnosis_id": "selected-panel",
            "asp_category": "rna",
            "analysis_intents": ["somatic"],
            "filters": {
                "somatic": {
                    "fusion": {
                        "fusion_descriptions": ["known", "matched-normal"],
                    }
                }
            },
        },
        assay_config={
            **_release("fusion", "hema", rna=True),
            "asp_group": "hema",
            "reporting": {
                "report_header": "RNA fusion report",
                "report_method": "RNA fusion analysis",
            },
        },
        save=1,
        include_snapshot=True,
    )
    assert template == "smd/report_fusion.html"
    assert context["assay_config"]["reporting"]["report_method"] == "RNA fusion analysis"
    assert "analysis_method" not in context
    assert context["class_desc_short"][2] == "Potentiell klinisk signifikans"
    assert len(snapshot_rows) == 1
    assert snapshot_rows[0]["fusion"] == "KMT2A::AFF1"
    assert (
        workflow.persist_report(
            sample_id="S1",
            sample={"name": "S1"},
            report_num=1,
            report_id="RID-1",
            report_file="/tmp/r.html",
            html="<html/>",
            snapshot_rows=snapshot_rows,
            created_by="tester",
        )
        == "RID-1"
    )


def test_rna_report_rejects_fusion_without_exactly_one_selected_call():
    """RNA reports fail instead of selecting a legacy first-call fallback."""
    fusion = {
        "_id": "fusion-1",
        "gene1": "KMT2A",
        "gene2": "AFF1",
        "calls": [{"selected": 0}],
        "classification": {"class": 2},
    }

    with pytest.raises(ValueError, match="exactly one selected call"):
        rna_workflow.RNAWorkflowService._build_snapshot_rows([fusion])
