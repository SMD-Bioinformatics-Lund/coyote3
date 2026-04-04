"""Tests for DNA/RNA workflow service facades."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.core.workflows import dna_workflow, rna_workflow


@pytest.fixture(autouse=True)
def _reset_workflow_repositories():
    """Reset workflow singletons between tests."""
    dna_workflow.DNAWorkflowService._repository = None
    rna_workflow.RNAWorkflowService._repository = None
    yield
    dna_workflow.DNAWorkflowService._repository = None
    rna_workflow.RNAWorkflowService._repository = None


def test_dna_workflow_requires_repository():
    """DNA workflow raises if repository is not configured."""
    with pytest.raises(RuntimeError):
        dna_workflow.DNAWorkflowService._repo()


def test_dna_workflow_forwards_build_and_persist_calls(monkeypatch):
    """DNA workflow facade delegates to shared helpers."""
    repo = SimpleNamespace(name="repo")
    dna_workflow.DNAWorkflowService.set_repository(repo)
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

    assert dna_workflow.DNAWorkflowService.has_repository() is True
    assert dna_workflow.DNAWorkflowService.build_report_payload({}, {}, 1, True)[0] == "tpl.html"
    assert (
        dna_workflow.DNAWorkflowService.build_report_location({}, {"asp_group": "dna"}, "/base")[0]
        == "id"
    )
    dna_workflow.DNAWorkflowService.prepare_report_output("/tmp", "/tmp/report.html", logger="L")
    assert (
        dna_workflow.DNAWorkflowService.persist_report(
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
    dna_workflow.DNAWorkflowService.validate_report_inputs(
        "LOG", {"name": "S1"}, {"asp_group": "dna"}
    )

    assert calls["build"]["repository"] is repo
    assert calls["validate"][3] == "dna"
    assert calls["prepare"] == ("/tmp", "/tmp/report.html", "L")
    assert calls["persist"]["sample_id"] == "S1"


def test_rna_workflow_merge_and_persist_filters(monkeypatch):
    """RNA workflow normalizes and persists form filters."""
    repo = SimpleNamespace(
        update_sample_filters=lambda _id, filters: None,
        get_sample_by_id=lambda _id: {
            "filters": {"min_spanning_reads": 2, "min_spanning_pairs": 3}
        },
    )
    rna_workflow.RNAWorkflowService.set_repository(repo)
    calls = {}

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
    updated_sample, updated_filters = rna_workflow.RNAWorkflowService.persist_form_filters(
        {"_id": "sample-1", "filters": {}},
        form={},
        assay_config_schema={},
        request_form=req,
    )
    assert updated_sample["filters"]["min_spanning_reads"] == 2
    assert updated_filters["min_spanning_pairs"] == 3


def test_rna_workflow_build_context_and_query(monkeypatch):
    """RNA workflow builds filter context and fusion query payload."""
    repo = SimpleNamespace(get_isgl_by_ids=lambda _ids: {"L1": {"genes": ["TP53"]}})
    rna_workflow.RNAWorkflowService.set_repository(repo)
    calls = {}

    monkeypatch.setattr(rna_workflow, "create_fusioneffectlist", lambda values: values)
    monkeypatch.setattr(rna_workflow, "create_fusioncallers", lambda values: values)
    monkeypatch.setattr(
        rna_workflow.util,
        "common",
        SimpleNamespace(get_sample_effective_genes=lambda *_args: ({"TP53": True}, ["TP53"])),
        raising=False,
    )

    def _build_query(assay_group, settings):
        calls["query"] = (assay_group, settings)
        return {"ok": True}

    monkeypatch.setattr(rna_workflow, "build_fusion_query", _build_query)

    context = rna_workflow.RNAWorkflowService.compute_filter_context(
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
    repo = SimpleNamespace(
        get_sample_fusions=lambda _query: [dict(fusion_doc)],
        get_fusion_annotations=lambda fusion: ([{"text": "a"}], fusion.get("classification")),
    )
    rna_workflow.RNAWorkflowService.set_repository(repo)

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

    rows = rna_workflow.RNAWorkflowService._build_snapshot_rows([fusion_doc])
    assert rows[0]["simple_id"] == "KMT2A::AFF1::chr11:1::chr4:2"
    assert rows[0]["created_on"] == "NOW"

    template, context, snapshot_rows = rna_workflow.RNAWorkflowService.build_report_payload(
        {"_id": "S1", "name": "S1"},
        save=1,
        include_snapshot=True,
    )
    assert template == "report_fusion.html"
    assert context["analysis_method"] == "method:hema"
    assert len(snapshot_rows) == 1
    assert (
        rna_workflow.RNAWorkflowService.persist_report(
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
