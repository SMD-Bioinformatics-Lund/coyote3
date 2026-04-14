"""Behavior tests for RNA API routes using collection-shaped fixtures."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.extensions import store
from api.main import app as api_app
from api.routers import fusions as rna
from api.services.common.change_payload import change_payload
from api.services.rna import expression_analysis as rna_service_module
from api.services.rna.expression_analysis import RnaService
from tests.fixtures.api import mock_collections as fx


class _Req:
    """Provide  Req behavior."""

    class _URL:
        """Provide  URL behavior."""

        path = "/api/v1/samples/S1/fusions"

    url = _URL()


def _rna_service() -> RnaService:
    return RnaService(
        assay_panel_handler=store.assay_panel_handler,
        gene_list_handler=store.gene_list_handler,
        sample_handler=store.sample_handler,
        fusion_handler=store.fusion_handler,
        rna_expression_handler=store.rna_expression_handler,
        rna_classification_handler=store.rna_classification_handler,
        rna_quality_handler=store.rna_quality_handler,
        annotation_handler=store.annotation_handler,
        reported_variant_handler=store.reported_variant_handler,
    )


def test_change_payload_shape():
    """Test change payload shape.

    Returns:
        The function result.
    """
    payload = change_payload(sample_id="S1", resource="fusion", resource_id="F1", action="flag")
    assert payload["status"] == "ok"
    assert payload["resource"] == "fusion"
    assert payload["resource_id"] == "F1"


def test_list_rna_fusions_success(monkeypatch):
    """Test list rna fusions success.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    assay_config = {**fx.assay_config_doc(), "asp_group": "rna", "analysis_types": ["FUSION"]}
    merged_sample = {**sample, "filters": {"min_spanning_reads": 3, "min_spanning_pairs": 2}}
    filter_context = {
        "checked_fusionlists": ["gl1"],
        "genes_covered_in_panel": {"gl1": ["EML4", "ALK"]},
        "filter_genes": ["EML4", "ALK"],
    }
    fusions = [fx.fusion_doc()]
    service = _rna_service()

    monkeypatch.setattr(rna, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(rna_service_module, "get_formatted_assay_config", lambda s: assay_config)
    monkeypatch.setattr(
        rna_service_module.RNAWorkflowService,
        "merge_and_normalize_sample_filters",
        lambda self, s, a, sid, lists: (merged_sample, merged_sample["filters"]),
    )
    monkeypatch.setattr(
        store.assay_panel_handler,
        "get_asp",
        lambda asp_name: {"asp_id": "asp1", "asp_group": "rna"},
    )
    monkeypatch.setattr(
        store.gene_list_handler,
        "get_isgl_by_asp",
        lambda assay, is_active=True, list_type=None: [fx.isgl_doc()],
    )
    monkeypatch.setattr(
        rna.util.common,
        "get_case_and_control_sample_ids",
        lambda s: {"case": "C1", "control": "C2"},
    )
    monkeypatch.setattr(store.sample_handler, "hidden_sample_comments", lambda oid: False)
    monkeypatch.setattr(
        rna_service_module.RNAWorkflowService,
        "compute_filter_context",
        lambda self, sample, sample_filters, assay_panel_doc: filter_context,
    )
    monkeypatch.setattr(
        rna_service_module.RNAWorkflowService,
        "build_fusion_list_query",
        lambda self, **kwargs: {"query": "ok"},
    )
    monkeypatch.setattr(store.fusion_handler, "get_sample_fusions", lambda query: fusions)
    monkeypatch.setattr(
        rna_service_module,
        "add_global_annotations",
        lambda fusions, assay_group, subpanel, annotation_handler=None: (fusions, fusions),
    )
    monkeypatch.setattr(
        rna_service_module.RNAWorkflowService,
        "attach_rna_analysis_sections",
        lambda self, s: s,
    )
    monkeypatch.setattr(
        rna_service_module, "generate_summary_text", lambda *args, **kwargs: "summary"
    )
    monkeypatch.setattr(rna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = rna.list_rna_fusions(_Req(), "S1", user=fx.api_user(), service=service)
    assert payload["meta"]["count"] == 1
    assert payload["fusions"][0]["gene1"] == fusions[0]["gene1"]
    assert payload["ai_text"] == "summary"


def test_show_rna_fusion_not_found_raises_404(monkeypatch):
    """Test show rna fusion not found raises 404.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    service = _rna_service()
    monkeypatch.setattr(rna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(store.fusion_handler, "get_fusion", lambda fusion_id: None)

    with pytest.raises(HTTPException) as exc:
        rna.show_rna_fusion("S1", "F404", user=fx.api_user(), service=service)

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Fusion not found"


def test_restful_rna_mutation_routes_are_registered():
    """Test restful rna mutation routes are registered.

    Returns:
        The function result.
    """
    paths = {route.path for route in api_app.routes}
    assert "/api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/false-positive" in paths
    assert (
        "/api/v1/samples/{sample_id}/fusions/{fusion_id}/selection/{callidx}/{num_calls}" in paths
    )
    assert "/api/v1/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hidden" in paths
    assert "/api/v1/samples/{sample_id}/fusions/flags/false-positive" in paths
    assert "/api/v1/samples/{sample_id}/fusions/flags/irrelevant" in paths
