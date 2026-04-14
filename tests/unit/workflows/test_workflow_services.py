"""Tests for DNA/RNA workflow service facades."""

from __future__ import annotations

from types import SimpleNamespace

from api.services.reporting import dna_workflow, rna_workflow


def _dna_workflow() -> dna_workflow.DNAWorkflowService:
    stub = SimpleNamespace()
    return dna_workflow.DNAWorkflowService(
        assay_panel_handler=stub,
        gene_list_handler=stub,
        variant_handler=stub,
        blacklist_handler=stub,
        sample_handler=stub,
        copy_number_variant_handler=stub,
        biomarker_handler=stub,
        translocation_handler=stub,
        vep_metadata_handler=stub,
        annotation_handler=stub,
        reported_variant_handler=stub,
    )


def _rna_workflow(
    *,
    sample_handler=None,
    gene_list_handler=None,
    rna_expression_handler=None,
    rna_classification_handler=None,
    rna_quality_handler=None,
    fusion_handler=None,
    annotation_handler=None,
    assay_panel_handler=None,
    reported_variant_handler=None,
) -> rna_workflow.RNAWorkflowService:
    stub = SimpleNamespace()
    return rna_workflow.RNAWorkflowService(
        sample_handler=sample_handler or stub,
        gene_list_handler=gene_list_handler or stub,
        rna_expression_handler=rna_expression_handler or stub,
        rna_classification_handler=rna_classification_handler or stub,
        rna_quality_handler=rna_quality_handler or stub,
        fusion_handler=fusion_handler or stub,
        annotation_handler=annotation_handler or stub,
        assay_panel_handler=assay_panel_handler or stub,
        reported_variant_handler=reported_variant_handler or stub,
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


def test_dna_report_payload_requires_sample_vep_version():
    try:
        dna_workflow.build_dna_report_payload(
            sample={
                "_id": "s1",
                "name": "S1",
                "assay": "assay_1",
                "subpanel": "hema",
                "filters": {
                    "genelists": [],
                    "vep_consequences": ["missense"],
                    "max_freq": 1,
                    "min_freq": 0,
                    "max_control_freq": 0.05,
                    "min_depth": 10,
                    "min_alt_reads": 3,
                    "max_popfreq": 0.05,
                },
            },
            assay_config={
                "asp_group": "hematology",
                "filters": {
                    "genelists": [],
                    "vep_consequences": ["missense"],
                    "max_freq": 1,
                    "min_freq": 0,
                    "max_control_freq": 0.05,
                    "min_depth": 10,
                    "min_alt_reads": 3,
                    "max_popfreq": 0.05,
                },
                "reporting": {"report_sections": ["SNV"], "report_header": "Demo"},
            },
            assay_panel_handler=SimpleNamespace(get_asp=lambda asp_name: {"asp_name": asp_name}),
            gene_list_handler=SimpleNamespace(
                get_isgl_by_asp=lambda assay, is_active=True: [],
                get_isgl_by_ids=lambda ids: {},
            ),
            variant_handler=SimpleNamespace(get_case_variants=lambda query: []),
            blacklist_handler=SimpleNamespace(add_blacklist_data=lambda rows, assay=None: rows),
            sample_handler=SimpleNamespace(get_latest_sample_comment=lambda sample_id: None),
            copy_number_variant_handler=SimpleNamespace(
                get_interesting_sample_cnvs=lambda sample_id: []
            ),
            biomarker_handler=SimpleNamespace(get_sample_biomarkers=lambda sample_id: []),
            translocation_handler=SimpleNamespace(
                get_interesting_sample_translocations=lambda sample_id: []
            ),
            vep_metadata_handler=SimpleNamespace(
                get_consequence_group_map=lambda version: {},
                get_variant_class_translations=lambda version: {},
            ),
            annotation_handler=SimpleNamespace(),
        )
    except ValueError as exc:
        assert str(exc) == "sample.vep_version is required for DNA report generation"
    else:
        raise AssertionError("Expected DNA report payload generation to require sample.vep_version")


def test_dna_report_payload_filters_reported_cnvs_by_selected_cnv_genelist():
    template_name, context, snapshot_rows = dna_workflow.build_dna_report_payload(
        sample={
            "_id": "s1",
            "name": "S1",
            "assay": "assay_1",
            "subpanel": "hema",
            "vep_version": "110",
            "filters": {
                "genelists": [],
                "vep_consequences": ["missense"],
                "cnv_genelists": ["CNV_GL"],
                "cnveffects": ["gain", "loss"],
                "max_freq": 1,
                "min_freq": 0,
                "max_control_freq": 0.05,
                "min_depth": 10,
                "min_alt_reads": 3,
                "max_popfreq": 0.05,
            },
        },
        assay_config={
            "asp_group": "hematology",
            "filters": {
                "genelists": [],
                "vep_consequences": ["missense"],
                "cnv_genelists": [],
                "cnveffects": ["gain", "loss"],
                "max_freq": 1,
                "min_freq": 0,
                "max_control_freq": 0.05,
                "min_depth": 10,
                "min_alt_reads": 3,
                "max_popfreq": 0.05,
            },
            "reporting": {"report_sections": ["SNV", "CNV"], "report_header": "Demo"},
        },
        assay_panel_handler=SimpleNamespace(
            get_asp=lambda asp_name: {"asp_name": asp_name, "covered_genes": ["TP53", "EGFR"]}
        ),
        gene_list_handler=SimpleNamespace(
            get_isgl_by_asp=lambda assay, is_active=True: [],
            get_isgl_by_ids=lambda ids: {
                "CNV_GL": {"displayname": "CNV GL", "is_active": True, "genes": ["TP53"]}
            },
        ),
        variant_handler=SimpleNamespace(get_case_variants=lambda query: []),
        blacklist_handler=SimpleNamespace(add_blacklist_data=lambda rows, assay=None: rows),
        sample_handler=SimpleNamespace(get_latest_sample_comment=lambda sample_id: None),
        copy_number_variant_handler=SimpleNamespace(
            get_interesting_sample_cnvs=lambda sample_id: [
                {"_id": "cnv1", "genes": [{"gene": "TP53", "class": 1}], "ratio": 0.7},
                {"_id": "cnv2", "genes": [{"gene": "EGFR", "class": 1}], "ratio": 0.8},
            ]
        ),
        biomarker_handler=SimpleNamespace(get_sample_biomarkers=lambda sample_id: []),
        translocation_handler=SimpleNamespace(
            get_interesting_sample_translocations=lambda sample_id: []
        ),
        vep_metadata_handler=SimpleNamespace(
            get_consequence_group_map=lambda version: {"missense": ["missense_variant"]},
            get_variant_class_translations=lambda version: {},
        ),
        annotation_handler=SimpleNamespace(),
    )

    assert template_name == "dna_report.html"
    assert snapshot_rows == []
    assert [cnv["_id"] for cnv in context["report_sections_data"]["cnvs"]] == ["cnv1"]


def test_rna_workflow_merge_and_persist_filters(monkeypatch):
    """RNA workflow normalizes and persists form filters."""
    calls = {}
    sample_handler = SimpleNamespace(
        update_sample_filters=lambda _id, filters: None,
        get_sample=lambda _id: {"filters": {"min_spanning_reads": 2, "min_spanning_pairs": 3}},
    )

    monkeypatch.setattr(
        rna_workflow.util,
        "common",
        SimpleNamespace(
            merge_sample_settings_with_assay_config=lambda sample, assay: {
                "name": "S1",
                "filters": {},
            },
            format_filters_from_form=lambda form, schema: {
                "fusion_effects": [],
                "fusion_callers": [],
            },
        ),
        raising=False,
    )
    monkeypatch.setattr(
        rna_workflow,
        "validate_rna_filter_inputs",
        lambda logger, sample_name, filters: calls.setdefault(
            "validate", (logger, sample_name, filters)
        ),
    )
    monkeypatch.setattr(rna_workflow, "normalize_rna_filter_keys", lambda payload: dict(payload))
    monkeypatch.setattr(rna_workflow, "create_fusioncallers", lambda values: values)
    monkeypatch.setattr(rna_workflow, "create_fusioneffectlist", lambda values: values)

    merged, normalized = rna_workflow.RNAWorkflowService.merge_and_normalize_sample_filters(
        {"name": "S1"},
        {"assay_name": "RNA"},
        "S1",
        logger="LOG",
    )
    assert merged["name"] == "S1"
    assert normalized == {}
    assert calls["validate"][1] == "S1"

    req = SimpleNamespace(getlist=lambda _key: ["L1"])
    workflow = _rna_workflow(sample_handler=sample_handler)
    updated_sample, updated_filters = workflow.persist_form_filters(
        {"_id": "sample-1", "filters": {}},
        form={},
        assay_config_schema={},
        request_form=req,
    )
    assert updated_sample["filters"]["min_spanning_reads"] == 2
    assert updated_filters["min_spanning_pairs"] == 3


def test_rna_workflow_build_context_and_query(monkeypatch):
    """RNA workflow builds filter context and fusion query payload."""
    calls = {}
    workflow = _rna_workflow(
        gene_list_handler=SimpleNamespace(get_isgl_by_ids=lambda _ids: {"L1": {"genes": ["TP53"]}})
    )

    monkeypatch.setattr(rna_workflow, "create_fusioneffectlist", lambda values: values)
    monkeypatch.setattr(rna_workflow, "create_fusioncallers", lambda values: values)
    monkeypatch.setattr(
        rna_workflow.util,
        "common",
        SimpleNamespace(
            get_sample_effective_genes=lambda *_args, **_kw: ({"TP53": True}, ["TP53"])
        ),
        raising=False,
    )

    def _build_query(assay_group, settings):
        calls["query"] = (assay_group, settings)
        return {"ok": True}

    monkeypatch.setattr(rna_workflow, "build_fusion_query", _build_query)

    context = workflow.compute_filter_context(
        {"name": "S1", "filters": {}},
        {"fusion_effects": ["in-frame"], "fusion_callers": ["arriba"], "fusionlists": ["L1"]},
        {"asp_id": "RNA"},
    )
    query = rna_workflow.RNAWorkflowService.build_fusion_list_query(
        "hema",
        "sample-1",
        {"min_spanning_reads": 2, "min_spanning_pairs": 3},
        context,
    )

    assert context["fusion_effect_form_keys"] == ["inframe"]
    assert context["filter_genes"] == ["TP53"]
    assert query == {"ok": True}
    assert calls["query"][0] == "hema"
    assert calls["query"][1]["id"] == "sample-1"


def test_rna_snapshot_rows_and_report_payload(monkeypatch):
    """RNA workflow builds snapshot rows and report payload."""
    fusion_doc = {
        "_id": "f1",
        "gene1": "KMT2A",
        "gene2": "AFF1",
        "calls": [{"selected": 1, "breakpoint1": "chr11:1", "breakpoint2": "chr4:2"}],
        "classification": {"class": 2, "_id": "ann1"},
    }
    fusion_handler = SimpleNamespace(
        get_sample_fusions=lambda _query: [dict(fusion_doc)],
        get_fusion_annotations=lambda fusion: ([{"text": "a"}], fusion.get("classification")),
    )

    monkeypatch.setattr(rna_workflow, "utc_now", lambda: "NOW")
    monkeypatch.setattr(
        rna_workflow.util,
        "common",
        SimpleNamespace(
            get_assay_from_sample=lambda sample: "hema",
            get_analysis_method=lambda assay: f"method:{assay}",
            get_report_header=lambda assay, sample: f"{assay}:{sample.get('name')}",
        ),
        raising=False,
    )
    monkeypatch.setattr(
        rna_workflow,
        "app",
        SimpleNamespace(
            config={
                "REPORT_CONFIG": {
                    "CLASS_DESC": {"2": "Tier II"},
                    "CLASS_DESC_SHORT": {"2": "T2"},
                    "ANALYSIS_DESCRIPTION": {"hema": "desc"},
                }
            }
        ),
    )
    monkeypatch.setattr(
        rna_workflow,
        "persist_shared_report_and_snapshot",
        lambda **kwargs: kwargs["report_id"],
    )

    workflow = _rna_workflow(
        fusion_handler=fusion_handler,
        sample_handler=SimpleNamespace(),
        reported_variant_handler=SimpleNamespace(),
    )
    rows = workflow._build_snapshot_rows([fusion_doc])
    assert rows[0]["simple_id"] == "KMT2A::AFF1::chr11:1::chr4:2"
    assert rows[0]["created_on"] == "NOW"

    template, context, snapshot_rows = workflow.build_report_payload(
        {"_id": "S1", "name": "S1"},
        save=1,
        include_snapshot=True,
    )
    assert template == "report_fusion.html"
    assert context["analysis_method"] == "method:hema"
    assert len(snapshot_rows) == 1
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
