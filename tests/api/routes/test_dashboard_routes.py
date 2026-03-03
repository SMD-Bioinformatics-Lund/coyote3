"""Behavior tests for Dashboard API routes."""

from __future__ import annotations

from api.routes import dashboard
from tests.api.fixtures import mock_collections as fx


def test_dashboard_summary_aggregates_counts(monkeypatch):
    monkeypatch.setattr(dashboard.store.sample_handler, "get_all_sample_counts", lambda report=False: 8 if report else 10)
    monkeypatch.setattr(
        dashboard.store.sample_handler,
        "get_assay_specific_sample_stats",
        lambda assays: {"WGS": len(assays)},
    )
    monkeypatch.setattr(dashboard.store.variant_handler, "get_total_variant_counts", lambda: 100)
    monkeypatch.setattr(dashboard.store.variant_handler, "get_total_snp_counts", lambda: 60)
    monkeypatch.setattr(dashboard.store.cnv_handler, "get_total_cnv_count", lambda: 5)
    monkeypatch.setattr(dashboard.store.transloc_handler, "get_total_transloc_count", lambda: 2)
    monkeypatch.setattr(dashboard.store.fusion_handler, "get_total_fusion_count", lambda: 3)
    monkeypatch.setattr(dashboard.store.blacklist_handler, "get_unique_blacklist_count", lambda: 4)
    monkeypatch.setattr(dashboard.store.variant_handler, "get_fp_counts", lambda: {"fp": 1})
    monkeypatch.setattr(dashboard.store.asp_handler, "get_all_asps_unique_gene_count", lambda: 250)
    monkeypatch.setattr(dashboard.store.asp_handler, "get_all_asp_gene_counts", lambda: {"dna": {"WGS": 120}})
    monkeypatch.setattr(
        dashboard.util.dashboard,
        "format_asp_gene_stats",
        lambda stats: {"formatted": stats},
    )
    monkeypatch.setattr(dashboard.store.sample_handler, "get_profile_counts", lambda: {"prod": 7})
    monkeypatch.setattr(dashboard.store.sample_handler, "get_omics_counts", lambda: {"dna": 6})
    monkeypatch.setattr(dashboard.store.sample_handler, "get_sequencing_scope_counts", lambda: {"tumor": 5})
    monkeypatch.setattr(dashboard.store.sample_handler, "get_paired_sample_counts", lambda: {"paired": 2})
    monkeypatch.setattr(dashboard.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dashboard.dashboard_summary(user=fx.api_user())

    assert payload["total_samples"] == 10
    assert payload["analysed_samples"] == 8
    assert payload["pending_samples"] == 2
    assert payload["variant_stats"]["total_variants"] == 100
    assert payload["sample_stats"]["profiles"]["prod"] == 7
