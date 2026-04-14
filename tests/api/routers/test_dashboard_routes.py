"""Behavior tests for Dashboard API routes."""

from __future__ import annotations

from api.routers import dashboard
from tests.fixtures.api import mock_collections as fx
from tests.unit.test_dashboard_service import _dashboard_service, _DashboardBackendStub


def test_dashboard_summary_aggregates_counts(monkeypatch):
    """Test dashboard summary aggregates counts.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    captured_calls: list = []
    service = _dashboard_service(backend=_DashboardBackendStub())
    monkeypatch.setattr(
        service.sample_handler,
        "get_dashboard_sample_rollup",
        lambda assays: (
            captured_calls.append(assays)
            or {
                "total_samples": 10 if assays is None else 3,
                "analysed_samples": 8 if assays is None else 2,
                "pending_samples": 2 if assays is None else 1,
                "user_samples_stats": {
                    "WGS": {
                        "total": 999 if assays is None else len(assays),
                        "analysed": 1,
                        "pending": 0,
                    }
                },
                "sample_stats": {
                    "profiles": {"prod": 7},
                    "omics_layers": {"dna": 6},
                    "sequencing_scopes": {"tumor": 5},
                    "pair_count": {"paired": 2, "unpaired": 0, "unknown": 0},
                },
            }
        ),
    )
    monkeypatch.setattr(
        service.variant_handler,
        "get_dashboard_variant_counts",
        lambda: {"total_variants": 100, "total_snps": 60, "fps": 1},
    )
    monkeypatch.setattr(
        service.variant_handler,
        "get_unique_variant_quality_counts",
        lambda: {"unique_total_variants": 50, "unique_fp_variants": 5},
    )
    monkeypatch.setattr(service.copy_number_variant_handler, "get_total_cnv_count", lambda: 5)
    monkeypatch.setattr(service.translocation_handler, "get_total_transloc_count", lambda: 2)
    monkeypatch.setattr(service.fusion_handler, "get_total_fusion_count", lambda: 3)
    monkeypatch.setattr(service.blacklist_handler, "get_unique_blacklist_count", lambda: 4)
    monkeypatch.setattr(
        service.reported_variant_handler,
        "get_dashboard_tier_stats",
        lambda: {"total": {"tier1": 1, "tier2": 2, "tier3": 3, "tier4": 4}, "by_assay": {}},
    )
    monkeypatch.setattr(service.assay_panel_handler, "get_all_asps_unique_gene_count", lambda: 250)
    monkeypatch.setattr(
        service.assay_panel_handler, "get_all_asp_gene_counts", lambda: {"dna": {"WGS": 120}}
    )
    monkeypatch.setattr(
        dashboard.util.dashboard,
        "format_asp_gene_stats",
        lambda stats: {"formatted": stats},
    )
    monkeypatch.setattr(dashboard.util.common, "convert_to_serializable", lambda payload: payload)
    monkeypatch.setattr(
        service,
        "build_admin_insights",
        lambda: {"counts": {"users_total": 11}},
    )
    monkeypatch.setattr(
        service,
        "build_capacity_counts",
        lambda: {
            "users_total": 10,
            "roles_total": 4,
            "asps_total": 6,
            "aspcs_total": 12,
            "isgl_total": 8,
        },
    )
    monkeypatch.setattr(
        service,
        "build_isgl_visibility",
        lambda isgls=None: {"public_only": 1, "private_only": 2, "adhoc_only": 3},
    )
    monkeypatch.setattr(
        service.gene_list_handler,
        "get_dashboard_assay_association_rollup",
        lambda: {"assay_isgl_counts": []},
    )

    payload = dashboard.dashboard_summary(user=fx.api_user(), service=service)

    assert payload["total_samples"] == 10
    assert payload["analysed_samples"] == 8
    assert payload["pending_samples"] == 2
    assert payload["variant_stats"]["total_variants"] == 100
    assert payload["sample_stats"]["profiles"]["prod"] == 7
    assert payload["tier_stats"]["total"]["tier3"] == 3
    assert payload["quality_stats"]["analysed_rate_percent"] == 80.0
    assert payload["admin_insights"]["counts"]["users_total"] == 11
    assert payload["capacity_counts"]["roles_total"] == 4
    assert payload["isgl_visibility"]["private_only"] == 2
    assert captured_calls[0] is None


def test_dashboard_summary_scopes_non_admin_from_assays_and_groups(monkeypatch):
    """Test dashboard summary scopes non admin from assays and groups.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    captured = {"calls": []}
    service = _dashboard_service(backend=_DashboardBackendStub())

    monkeypatch.setattr(
        service.sample_handler,
        "get_dashboard_sample_rollup",
        lambda assays: (
            captured["calls"].append(assays)
            or {
                "total_samples": 10 if assays is None else 1,
                "analysed_samples": 9 if assays is None else 1,
                "pending_samples": 1 if assays is None else 0,
                "user_samples_stats": {"rna-fusion": {"total": 1, "analysed": 1, "pending": 0}},
                "sample_stats": {"profiles": {"production": 10}},
            }
        ),
    )
    monkeypatch.setattr(
        service.assay_panel_handler,
        "resolve_active_asp_ids_for_scope",
        lambda assays, groups: ["myeloid_gmsv1"] if "myeloid" in groups else [],
    )
    monkeypatch.setattr(
        service.variant_handler,
        "get_dashboard_variant_counts",
        lambda: {"total_variants": 0, "total_snps": 0, "fps": 0},
    )
    monkeypatch.setattr(
        service.variant_handler,
        "get_unique_variant_quality_counts",
        lambda: {"unique_total_variants": 0, "unique_fp_variants": 0},
    )
    monkeypatch.setattr(service.copy_number_variant_handler, "get_total_cnv_count", lambda: 0)
    monkeypatch.setattr(service.translocation_handler, "get_total_transloc_count", lambda: 0)
    monkeypatch.setattr(service.fusion_handler, "get_total_fusion_count", lambda: 0)
    monkeypatch.setattr(service.blacklist_handler, "get_unique_blacklist_count", lambda: 0)
    monkeypatch.setattr(
        service.reported_variant_handler,
        "get_dashboard_tier_stats",
        lambda: {"total": {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}, "by_assay": {}},
    )
    monkeypatch.setattr(service.assay_panel_handler, "get_all_asps_unique_gene_count", lambda: 0)
    monkeypatch.setattr(service.assay_panel_handler, "get_all_asp_gene_counts", lambda: {})
    monkeypatch.setattr(dashboard.util.dashboard, "format_asp_gene_stats", lambda stats: stats)
    monkeypatch.setattr(dashboard.util.common, "convert_to_serializable", lambda payload: payload)
    monkeypatch.setattr(
        service,
        "build_admin_insights",
        lambda: {"counts": {"users_total": 999}},
    )
    monkeypatch.setattr(
        service,
        "build_capacity_counts",
        lambda: {
            "users_total": 2,
            "roles_total": 1,
            "asps_total": 3,
            "aspcs_total": 4,
            "isgl_total": 5,
        },
    )
    monkeypatch.setattr(
        service,
        "build_isgl_visibility",
        lambda isgls=None: {"public_only": 5},
    )
    monkeypatch.setattr(
        service.gene_list_handler,
        "get_dashboard_assay_association_rollup",
        lambda: {"assay_isgl_counts": []},
    )

    user = fx.api_user()
    user.role = "user"
    user.roles = ["user"]
    user.assays = ["rna-fusion"]
    user.assay_groups = ["myeloid"]
    monkeypatch.setattr(
        service.user_handler,
        "user_with_id",
        lambda _id: {
            "role": "user",
            "roles": ["user"],
            "assays": ["rna-fusion"],
            "assay_groups": ["myeloid"],
        },
    )
    payload = dashboard.dashboard_summary(user=user, service=service)

    scoped_assays = captured["calls"][1]
    assert captured["calls"][0] is None
    assert "rna-fusion" in scoped_assays
    assert "myeloid_gmsv1" in scoped_assays
    assert payload["dashboard_meta"]["scope_assays"] == scoped_assays
    assert payload["total_samples"] == 10
    assert payload["sample_stats"]["profiles"]["production"] == 10
    assert payload["admin_insights"] == {}
    assert payload["capacity_counts"]["users_total"] == 2
    assert payload["isgl_visibility"]["public_only"] == 5


def test_dashboard_summary_admin_scope_is_unfiltered(monkeypatch):
    """Test dashboard summary admin scope is unfiltered.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    captured = {"calls": []}
    service = _dashboard_service(backend=_DashboardBackendStub())
    monkeypatch.setattr(
        service.sample_handler,
        "get_dashboard_sample_rollup",
        lambda assays: (
            captured["calls"].append(assays)
            or {
                "total_samples": 2,
                "analysed_samples": 1,
                "pending_samples": 1,
                "user_samples_stats": {},
                "sample_stats": {},
            }
        ),
    )
    monkeypatch.setattr(
        service.variant_handler,
        "get_dashboard_variant_counts",
        lambda: {"total_variants": 0, "total_snps": 0, "fps": 0},
    )
    monkeypatch.setattr(
        service.variant_handler,
        "get_unique_variant_quality_counts",
        lambda: {"unique_total_variants": 0, "unique_fp_variants": 0},
    )
    monkeypatch.setattr(service.copy_number_variant_handler, "get_total_cnv_count", lambda: 0)
    monkeypatch.setattr(service.translocation_handler, "get_total_transloc_count", lambda: 0)
    monkeypatch.setattr(service.fusion_handler, "get_total_fusion_count", lambda: 0)
    monkeypatch.setattr(service.blacklist_handler, "get_unique_blacklist_count", lambda: 0)
    monkeypatch.setattr(
        service.reported_variant_handler,
        "get_dashboard_tier_stats",
        lambda: {"total": {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}, "by_assay": {}},
    )
    monkeypatch.setattr(service.assay_panel_handler, "get_all_asps_unique_gene_count", lambda: 0)
    monkeypatch.setattr(service.assay_panel_handler, "get_all_asp_gene_counts", lambda: {})
    monkeypatch.setattr(dashboard.util.dashboard, "format_asp_gene_stats", lambda stats: stats)
    monkeypatch.setattr(dashboard.util.common, "convert_to_serializable", lambda payload: payload)
    monkeypatch.setattr(
        service,
        "build_admin_insights",
        lambda: {"counts": {"users_total": 1}},
    )
    monkeypatch.setattr(
        service,
        "build_capacity_counts",
        lambda: {
            "users_total": 7,
            "roles_total": 3,
            "asps_total": 2,
            "aspcs_total": 2,
            "isgl_total": 1,
        },
    )
    monkeypatch.setattr(
        service,
        "build_isgl_visibility",
        lambda isgls=None: {"public_private_adhoc": 9},
    )
    monkeypatch.setattr(
        service.gene_list_handler,
        "get_dashboard_assay_association_rollup",
        lambda: {"assay_isgl_counts": []},
    )

    user = fx.api_user()
    user.role = "admin"
    user.assays = ["solid_gmsv3"]
    user.assay_groups = ["solid"]
    monkeypatch.setattr(
        service.user_handler,
        "user_with_id",
        lambda _id: {"role": "admin", "assays": [], "assay_groups": []},
    )
    payload = dashboard.dashboard_summary(user=user, service=service)

    assert captured["calls"] == [None, None]
    assert payload["admin_insights"]["counts"]["users_total"] == 1
    assert payload["capacity_counts"]["users_total"] == 7
    assert payload["isgl_visibility"]["public_private_adhoc"] == 9
