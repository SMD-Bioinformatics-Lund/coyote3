"""Behavior tests for RNA API routes using collection-shaped fixtures."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routers import rna
from tests.api.fixtures import mock_collections as fx


class _Req:
    class _URL:
        path = "/api/v1/rna/samples/S1/fusions"

    url = _URL()


def test_mutation_payload_shape():
    payload = rna._mutation_payload("S1", "fusion", "F1", "flag")
    assert payload["status"] == "ok"
    assert payload["resource"] == "fusion"
    assert payload["resource_id"] == "F1"


def test_list_rna_fusions_success(monkeypatch):
    sample = fx.sample_doc()
    assay_config = {**fx.assay_config_doc(), "asp_group": "rna", "analysis_types": ["FUSION"]}
    merged_sample = {**sample, "filters": {"min_spanning_reads": 3, "min_spanning_pairs": 2}}
    filter_context = {
        "checked_fusionlists": ["gl1"],
        "genes_covered_in_panel": {"gl1": ["EML4", "ALK"]},
        "filter_genes": ["EML4", "ALK"],
    }
    fusions = [fx.fusion_doc()]

    monkeypatch.setattr(rna, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(rna, "_get_formatted_assay_config", lambda s: assay_config)
    monkeypatch.setattr(rna.RNAWorkflowService, "merge_and_normalize_sample_filters", lambda s, a, sid, l: (merged_sample, merged_sample["filters"]))
    monkeypatch.setattr(rna.store.schema_handler, "get_schema", lambda name: {"_id": name})
    monkeypatch.setattr(rna.store.asp_handler, "get_asp", lambda asp_name: {"_id": "asp1", "asp_group": "rna"})
    monkeypatch.setattr(rna.store.isgl_handler, "get_isgl_by_asp", lambda assay, is_active=True, list_type=None: [fx.isgl_doc()])
    monkeypatch.setattr(rna.util.common, "get_case_and_control_sample_ids", lambda s: {"case": "C1", "control": "C2"})
    monkeypatch.setattr(rna.store.sample_handler, "hidden_sample_comments", lambda oid: False)
    monkeypatch.setattr(rna.RNAWorkflowService, "compute_filter_context", lambda sample, sample_filters, assay_panel_doc: filter_context)
    monkeypatch.setattr(rna.RNAWorkflowService, "build_fusion_list_query", lambda **kwargs: {"query": "ok"})
    monkeypatch.setattr(rna.store.fusion_handler, "get_sample_fusions", lambda query: fusions)
    monkeypatch.setattr(rna, "add_global_annotations", lambda fusions, assay_group, subpanel: (fusions, fusions))
    monkeypatch.setattr(rna.RNAWorkflowService, "attach_rna_analysis_sections", lambda s: s)
    monkeypatch.setattr(rna, "generate_summary_text", lambda *args, **kwargs: "summary")
    monkeypatch.setattr(rna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = rna.list_rna_fusions(_Req(), "S1", user=fx.api_user())
    assert payload["meta"]["count"] == 1
    assert payload["fusions"][0]["gene1"] == fusions[0]["gene1"]
    assert payload["ai_text"] == "summary"


def test_show_rna_fusion_not_found_raises_404(monkeypatch):
    monkeypatch.setattr(rna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(rna.store.fusion_handler, "get_fusion", lambda fusion_id: None)

    with pytest.raises(HTTPException) as exc:
        rna.show_rna_fusion("S1", "F404", user=fx.api_user())

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Fusion not found"
