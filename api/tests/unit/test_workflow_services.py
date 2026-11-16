"""Tests for DNA/RNA workflow service facades."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from coyote.application.common.release_resources import capture_assay_resource, capture_gene_lists
from coyote.application.reporting import dna_workflow
from coyote_api.infra.report_images import get_plot


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


def _dna_workflow() -> dna_workflow.DNAWorkflowService:
    stub = SimpleNamespace()
    return dna_workflow.DNAWorkflowService(
        plot_reader=get_plot,
        assay_panel_repository=stub,
        gene_list_repository=stub,
        variant_repository=stub,
        blacklist_repository=stub,
        sample_repository=stub,
        diagnosis_repository=SimpleNamespace(
            get_current=lambda *args: {"display_name": "Synthetic diagnosis"}
        ),
        copy_number_variant_repository=stub,
        biomarker_repository=stub,
        translocation_repository=stub,
        vep_metadata_repository=stub,
        annotation_repository=stub,
        reported_variant_repository=stub,
        report_repository=stub,
        clinical_rule_service=None,
    )


def test_dna_workflow_forwards_build_and_persist_calls(monkeypatch):
    """DNA workflow facade delegates to shared helpers."""
    calls = {}

    def _build_payload(**kwargs):
        calls["build"] = kwargs
        return ("tpl.html", {}, [])

    monkeypatch.setattr(dna_workflow, "build_dna_report_payload", _build_payload)
    monkeypatch.setattr(
        dna_workflow,
        "prepare_shared_report_output",
        lambda report_path, report_file, logger=None: calls.setdefault(
            "prepare", (report_path, report_file, logger)
        ),
    )

    def _persist_payload(**kwargs):
        calls["persist"] = kwargs
        return "rid-1"

    monkeypatch.setattr(dna_workflow, "persist_shared_report_and_snapshot", _persist_payload)

    def _build_location(**kwargs):
        calls["location"] = kwargs
        return ("id", "/tmp", "/tmp/report.html")

    monkeypatch.setattr(dna_workflow, "build_report_file_location", _build_location)
    monkeypatch.setattr(
        dna_workflow,
        "validate_report_inputs",
        lambda logger, sample, assay_config, analyte: calls.setdefault(
            "validate", (logger, sample, assay_config, analyte)
        ),
    )

    workflow = _dna_workflow()
    assert workflow.build_report_payload({}, {}, 1, True)[0] == "tpl.html"
    assert workflow.build_report_location({}, {"asp_group": "dna"}, "/base")[0] == "id"
    workflow.prepare_report_output("/tmp", "/tmp/report.html", logger="L")
    assert (
        workflow.persist_report(
            sample_id="S1",
            sample={"name": "S1"},
            report_num=1,
            report_id="RID",
            report_file="/tmp/report.html",
            html="<html/>",
            snapshot_rows=[],
            created_by="tester",
        )
        == "rid-1"
    )
    workflow.validate_report_inputs("LOG", {"name": "S1"}, {"asp_group": "dna"})

    assert calls["validate"][3] == "dna"
    assert calls["prepare"] == ("/tmp", "/tmp/report.html", "L")
    assert calls["persist"]["sample_id"] == "S1"


def test_dna_report_payload_requires_sample_database_vep_version():
    try:
        dna_workflow.build_dna_report_payload(
            plot_reader=get_plot,
            sample={
                "_id": "s1",
                "name": "S1",
                "asp_id": "assay_1",
                "diagnosis_id": "hema",
                "filters": {
                    "somatic": {
                        "snv": {
                            "snvlists": [],
                            "vep_consequences": ["missense"],
                            "max_freq": 1,
                            "min_freq": 0,
                            "max_control_freq": 0.05,
                            "min_depth": 10,
                            "min_alt_reads": 3,
                            "max_popfreq": 0.05,
                        }
                    },
                },
            },
            assay_config={
                **_release("assay_1", "hematology"),
                "asp_group": "hematology",
                "filters": {
                    "somatic": {
                        "snv": {
                            "snvlists": [],
                            "vep_consequences": ["missense"],
                            "max_freq": 1,
                            "min_freq": 0,
                            "max_control_freq": 0.05,
                            "min_depth": 10,
                            "min_alt_reads": 3,
                            "max_popfreq": 0.05,
                        }
                    },
                },
                "reporting": {"report_sections": ["SNV"], "report_header": "Demo"},
            },
            assay_panel_repository=SimpleNamespace(get_asp=lambda asp_name: {"asp_name": asp_name}),
            gene_list_repository=SimpleNamespace(
                get_isgl_by_asp=lambda assay, is_active=True: [],
                get_isgl_by_ids=lambda ids: {},
            ),
            variant_repository=SimpleNamespace(get_case_variants=lambda query: []),
            blacklist_repository=SimpleNamespace(
                add_blacklist_data=lambda rows, group, *, asp_id: rows
            ),
            sample_repository=SimpleNamespace(get_latest_sample_comment=lambda sample_id: None),
            diagnosis_repository=SimpleNamespace(
                get_current=lambda *args: {"display_name": "Synthetic diagnosis"}
            ),
            copy_number_variant_repository=SimpleNamespace(get_sample_cnvs=lambda selection: []),
            biomarker_repository=SimpleNamespace(get_sample_biomarkers=lambda sample_id: []),
            translocation_repository=SimpleNamespace(
                get_sample_translocations=lambda sample_id: []
            ),
            vep_metadata_repository=SimpleNamespace(
                get_consequence_group_map=lambda version: {},
                get_variant_class_translations=lambda version: {},
            ),
            annotation_repository=SimpleNamespace(),
        )
    except ValueError as exc:
        assert str(exc) == "sample.database_versions.vep is required for DNA report generation"
    else:
        raise AssertionError(
            "Expected DNA report payload generation to require database_versions.vep"
        )


@pytest.mark.parametrize("mode,has_separate_germline", [("shared", False), ("independent", True)])
def test_dna_report_payload_excludes_false_positive_cnvs_and_applies_selected_cnv_list(
    mode, has_separate_germline
):
    evaluations = []

    def evaluate(**kwargs):
        evaluations.append(kwargs)
        return None

    template_name, context, snapshot_rows = dna_workflow.build_dna_report_payload(
        clinical_rule_service=SimpleNamespace(evaluate=evaluate),
        plot_reader=get_plot,
        sample={
            "_id": "s1",
            "analysis_intents": ["somatic", "germline"],
            "name": "S1",
            "asp_id": "assay_1",
            "diagnosis_id": "hema",
            "database_versions": {"vep": "110"},
            "filters": {
                "germline": {"snv": {}},
                "somatic": {
                    "snv": {
                        "snvlists": [],
                        "vep_consequences": ["missense"],
                        "max_freq": 1,
                        "min_freq": 0,
                        "max_control_freq": 0.05,
                        "min_depth": 10,
                        "min_alt_reads": 3,
                        "max_popfreq": 0.05,
                    },
                    "cnv": {"cnvlists": ["CNV_GL"], "cnveffects": ["gain", "loss"]},
                },
            },
        },
        assay_config={
            "snv_filter_mode": mode,
            **_release("assay_1", "hematology"),
            "asp_group": "hematology",
            "filters": {
                "germline": {"snv": {}},
                "somatic": {
                    "snv": {
                        "snvlists": [],
                        "vep_consequences": ["missense"],
                        "max_freq": 1,
                        "min_freq": 0,
                        "max_control_freq": 0.05,
                        "min_depth": 10,
                        "min_alt_reads": 3,
                        "max_popfreq": 0.05,
                    },
                    "cnv": {"cnvlists": [], "cnveffects": ["gain", "loss"]},
                },
            },
            "reporting": {"report_sections": ["SNV", "CNV"], "report_header": "Demo"},
        },
        assay_panel_repository=SimpleNamespace(
            get_asp=lambda asp_name: {"asp_name": asp_name, "covered_genes": ["TP53", "EGFR"]}
        ),
        gene_list_repository=SimpleNamespace(
            get_isgl_by_asp=lambda assay, is_active=True: [],
            get_isgl_by_ids=lambda ids: {
                "CNV_GL": {
                    "displayname": "CNV GL",
                    "is_active": True,
                    "list_type": ["cnv"],
                    "genes": ["TP53"],
                }
            },
        ),
        variant_repository=SimpleNamespace(
            get_case_variants=lambda query: [],
            hydrate_finding_comments_many=lambda rows: rows,
        ),
        blacklist_repository=SimpleNamespace(
            add_blacklist_data=lambda rows, group, *, asp_id: rows
        ),
        sample_repository=SimpleNamespace(get_latest_sample_comment=lambda sample_id: None),
        diagnosis_repository=SimpleNamespace(
            get_current=lambda *args: {"display_name": "Synthetic diagnosis"}
        ),
        copy_number_variant_repository=SimpleNamespace(
            get_sample_cnvs=lambda selection: [
                {
                    "_id": "cnv1",
                    "genes": [{"gene": "TP53", "class": 1}],
                    "ratio": 0.7,
                    "fp": True,
                },
                {"_id": "cnv2", "genes": [{"gene": "EGFR", "class": 1}], "ratio": 0.8},
                {
                    "_id": "cnv3",
                    "genes": [{"gene": "TP53", "class": 1}],
                    "ratio": 0.9,
                },
            ]
        ),
        biomarker_repository=SimpleNamespace(get_sample_biomarkers=lambda sample_id: []),
        translocation_repository=SimpleNamespace(get_sample_translocations=lambda sample_id: []),
        vep_metadata_repository=SimpleNamespace(
            get_consequence_group_map=lambda version: {"missense": ["missense_variant"]},
            get_variant_class_translations=lambda version: {},
        ),
        annotation_repository=SimpleNamespace(
            get_global_annotations=lambda *args, **kwargs: ([], {"class": 3}, [], {}),
            get_additional_classifications=lambda *args, **kwargs: [],
        ),
        include_snapshot=True,
    )

    assert template_name == "smd/dna_report.html"
    assert len(snapshot_rows) == 1
    assert snapshot_rows[0]["analysis_type"] == "CNV"
    assert snapshot_rows[0]["var_oid"] == "cnv3"
    assert snapshot_rows[0]["classification"] == 3
    assert [cnv["_id"] for cnv in context["report_sections_data"]["cnvs"]] == ["cnv3"]

    assert ("germline_snvs" in context["report_sections_data"]) is has_separate_germline
    assert evaluations[0]["context"].aggregates.cnv_count == 1
    if has_separate_germline:
        germline = evaluations[0]["intent_contexts"]["germline"]
        assert germline.sample.analysis_intent == "germline"
        assert germline.aggregates.finding_count == 0
        assert germline.aggregates.cnv_count == 0
        assert germline.findings == []
    else:
        assert "intent_contexts" not in evaluations[0]
