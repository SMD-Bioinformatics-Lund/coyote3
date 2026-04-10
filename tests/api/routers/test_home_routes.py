"""Behavior tests for sample list and sample workflow API routes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.extensions import store
from api.routers import samples
from api.services.sample import catalog as sample_catalog_service_module
from api.services.sample.catalog import SampleCatalogService
from tests.fixtures.api import mock_collections as fx


def _sample_catalog_service() -> SampleCatalogService:
    return SampleCatalogService(
        sample_handler=store.sample_handler,
        gene_list_handler=store.gene_list_handler,
        assay_panel_handler=store.assay_panel_handler,
        variant_handler=store.variant_handler,
        copy_number_variant_handler=store.copy_number_variant_handler,
        fusion_handler=store.fusion_handler,
        translocation_handler=store.translocation_handler,
        biomarker_handler=store.biomarker_handler,
        grouped_coverage_handler=store.grouped_coverage_handler,
    )


def test_home_samples_read_returns_live_and_done(monkeypatch):
    """Test home samples read returns live and done.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user = fx.api_user()
    calls = []
    service = _sample_catalog_service()

    def _get_samples(**kwargs):
        """Get samples.

        Args:
                **kwargs: Kwargs. Additional keyword arguments.

        Returns:
                The  get samples result.
        """
        calls.append(kwargs)
        if kwargs.get("report"):
            return [{"_id": "d1", "reports": [{"time_created": 123}]}, {"_id": "d2"}]
        return [{"_id": "l1"}, {"_id": "l2"}]

    monkeypatch.setattr(
        sample_catalog_service_module,
        "runtime_app",
        type("_App", (), {"config": {"REPORTED_SAMPLES_SEARCH_LIMIT": 50}})(),
    )
    monkeypatch.setattr(service.sample_handler, "get_samples", _get_samples)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = samples.list_samples_read(
        status="live",
        search_mode="both",
        sample_view=None,
        page=2,
        per_page=1,
        live_page=2,
        done_page=2,
        live_per_page=1,
        done_per_page=1,
        profile_scope="production",
        user=user,
        service=service,
    )
    assert len(payload["live_samples"]) == 1
    assert len(payload["done_samples"]) == 1
    assert payload["sample_view"] == "all"
    assert payload["live_page"] == 2
    assert payload["done_page"] == 2
    assert payload["live_per_page"] == 1
    assert payload["done_per_page"] == 1
    assert payload["profile_scope"] == "production"
    assert payload["has_next_live"] is True
    assert payload["has_next_done"] is True
    assert all(call["offset"] == 1 for call in calls)


def test_home_samples_read_always_fetches_both_tables(monkeypatch):
    """Test home samples read always fetches both tables.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    user = fx.api_user()
    calls = []
    service = _sample_catalog_service()

    def _get_samples(**kwargs):
        """Get samples.

        Args:
                **kwargs: Kwargs. Additional keyword arguments.

        Returns:
                The  get samples result.
        """
        calls.append(kwargs)
        return [{"_id": "d1", "reports": [{"time_created": 123}]}]

    monkeypatch.setattr(
        sample_catalog_service_module,
        "runtime_app",
        type("_App", (), {"config": {"REPORTED_SAMPLES_SEARCH_LIMIT": 50}})(),
    )
    monkeypatch.setattr(service.sample_handler, "get_samples", _get_samples)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = samples.list_samples_read(
        status="live",
        search_mode="live",
        sample_view="reported",
        page=1,
        per_page=30,
        live_page=1,
        done_page=1,
        live_per_page=30,
        done_per_page=30,
        profile_scope="all",
        user=user,
        service=service,
    )

    assert payload["sample_view"] == "all"
    assert payload["profile_scope"] == "all"
    assert len(payload["live_samples"]) == 1
    assert len(payload["done_samples"]) == 1
    assert len(calls) == 2
    assert any(call["report"] is True and call["status"] == "done" for call in calls)
    assert any(call["report"] is False and call["status"] == "live" for call in calls)


def test_home_apply_isgl_invalid_payload_raises_400(monkeypatch):
    """Test home apply isgl invalid payload raises 400.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())

    with pytest.raises(HTTPException) as exc:
        samples.sample_apply_genelists_change(
            "S1", payload={"isgl_ids": "bad"}, user=fx.api_user(), service=_sample_catalog_service()
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Invalid isgl_ids payload"


def test_home_save_adhoc_genes_mutation_parses_and_sorts(monkeypatch):
    """Test home save adhoc genes mutation parses and sorts.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    calls = {}
    service = _sample_catalog_service()

    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: sample)

    def _update_sample_filters(sample_id, filters):
        """Update sample filters.

        Args:
                sample_id: Sample id.
                filters: Filters.

        Returns:
                The  update sample filters result.
        """
        calls["filters"] = filters

    monkeypatch.setattr(service.sample_handler, "update_sample_filters", _update_sample_filters)
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)

    payload = samples.sample_save_adhoc_genes_change(
        "S1",
        payload={"genes": "NPM1 TP53\nIDH1", "label": "focus", "list_type": "cnv"},
        user=fx.api_user(),
        service=service,
    )

    assert payload["action"] == "save_adhoc_genes"
    assert payload["gene_count"] == 3
    assert payload["list_type"] == "cnv"
    assert calls["filters"]["adhoc_genes"]["cnv"]["genes"] == ["IDH1", "NPM1", "TP53"]
    assert calls["filters"]["adhoc_genes"]["cnv"]["label"] == "focus"


def test_edit_context_payload_includes_analysis_counts(monkeypatch):
    """Edit context should expose raw and gene-filtered counts for other analysis types too."""
    sample = fx.sample_doc()
    sample["_id"] = "s1"
    sample["omics_layer"] = "dna"
    sample["filters"]["genelists"] = ["gl1"]
    sample["filters"]["cnv_genelists"] = ["gl1"]
    sample["filters"]["adhoc_genes"] = {}
    service = _sample_catalog_service()

    monkeypatch.setattr(
        service.assay_panel_handler,
        "get_asp",
        lambda assay: {"asp_group": "dna", "covered_genes": ["TP53", "NPM1"]},
    )
    monkeypatch.setattr(
        sample_catalog_service_module,
        "get_formatted_assay_config",
        lambda sample_doc: {"filters": dict(sample_doc.get("filters") or {})},
    )
    monkeypatch.setattr(
        service.assay_panel_handler,
        "get_asp_genes",
        lambda assay: (["TP53", "NPM1"], []),
    )
    monkeypatch.setattr(
        service.gene_list_handler,
        "get_isgl_by_ids",
        lambda ids: {"gl1": {"genes": ["TP53"]}},
    )
    monkeypatch.setattr(
        service.variant_handler,
        "get_variant_stats",
        lambda sample_id, genes=None: {
            "variants": 10 if genes is None else 4,
            "interesting": 2 if genes is None else 1,
            "irrelevant": 1,
            "false_positives": 0,
        },
    )
    monkeypatch.setattr(
        service.copy_number_variant_handler,
        "get_sample_cnvs",
        lambda query: [
            {"genes": [{"gene": "TP53"}]},
            {"genes": [{"gene": "RUNX1"}]},
        ],
    )
    monkeypatch.setattr(
        service.translocation_handler,
        "get_sample_translocations",
        lambda sample_id: [
            {"INFO": [{"ANN": [{"Gene_Name": "TP53&ABL1"}]}]},
            {"INFO": [{"ANN": [{"Gene_Name": "RUNX1&ETV6"}]}]},
        ],
    )
    monkeypatch.setattr(
        service.fusion_handler,
        "get_sample_fusions",
        lambda query: [],
    )
    monkeypatch.setattr(
        service.biomarker_handler,
        "get_sample_biomarkers",
        lambda sample_id: [{"name": "TMB"}],
    )

    payload = service.edit_context_payload(sample=sample)

    assert payload["analysis_counts_raw"] == {
        "snv": 10,
        "cnv": 2,
        "transloc": 2,
        "fusion": 0,
        "biomarker": 1,
    }
    assert payload["analysis_counts_filtered"] == {
        "snv": 4,
        "cnv": 1,
        "transloc": 1,
        "fusion": 0,
        "biomarker": 1,
    }


def test_edit_context_payload_uses_assay_merged_filters_for_counts(monkeypatch):
    """Edit-context counts should use the same merged assay defaults as the findings page."""
    sample = fx.sample_doc()
    sample["_id"] = "s1"
    sample["omics_layer"] = "dna"
    sample["filters"]["genelists"] = []
    sample["filters"]["adhoc_genes"] = {}
    service = _sample_catalog_service()

    monkeypatch.setattr(
        sample_catalog_service_module,
        "get_formatted_assay_config",
        lambda sample_doc: {"filters": {"genelists": ["gl1"]}},
    )
    monkeypatch.setattr(
        service.assay_panel_handler,
        "get_asp",
        lambda assay: {"asp_group": "dna", "covered_genes": ["TP53", "NPM1"]},
    )
    monkeypatch.setattr(
        service.assay_panel_handler,
        "get_asp_genes",
        lambda assay: (["TP53", "NPM1"], []),
    )
    monkeypatch.setattr(
        service.gene_list_handler,
        "get_isgl_by_ids",
        lambda ids: {"gl1": {"genes": ["TP53"]}},
    )
    monkeypatch.setattr(
        service.variant_handler,
        "get_variant_stats",
        lambda sample_id, genes=None: {
            "variants": 6 if genes is None else 2,
            "interesting": 1,
            "irrelevant": 0,
            "false_positives": 0,
        },
    )
    monkeypatch.setattr(service.copy_number_variant_handler, "get_sample_cnvs", lambda query: [])
    monkeypatch.setattr(
        service.translocation_handler, "get_sample_translocations", lambda sample_id: []
    )
    monkeypatch.setattr(service.fusion_handler, "get_sample_fusions", lambda query: [])
    monkeypatch.setattr(service.biomarker_handler, "get_sample_biomarkers", lambda sample_id: [])

    payload = service.edit_context_payload(sample=sample)

    assert payload["sample"]["filters"]["genelists"] == ["gl1"]
    assert payload["analysis_counts_filtered"]["snv"] == 2
