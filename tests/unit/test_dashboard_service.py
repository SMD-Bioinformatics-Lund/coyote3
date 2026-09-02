"""Unit tests for dashboard service calculations and scope behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from api.application.dashboard.analytics import DashboardService, DashboardSnapshotUnavailable
from api.domain.common.dashboard import (
    format_panel_gene_stats,
    panel_asp_ids,
    summarize_panel_gene_stats,
)


class _DashboardBackendStub:
    def __init__(self) -> None:
        self.user_doc = {
            "role": "analyst",
            "roles": ["analyst"],
            "assays": ["A1"],
            "assay_groups": ["G1"],
        }

    def count_users(self):
        return 10

    def count_roles(self, is_active=None):  # noqa: ARG002
        return 3

    def count_asps(self, is_active=None):  # noqa: ARG002
        return 4

    def count_aspcs(self, is_active=None):  # noqa: ARG002
        return 5

    def get_dashboard_analysis_type_rollup(self, *, asp_ids):
        if asp_ids != ["A1"]:
            return []
        return [
            {"analysis_type": "SNV", "enabled": 2, "reportable": 2},
            {"analysis_type": "CNV", "enabled": 2, "reportable": 1},
        ]

    def count_isgls(self, is_active=None):  # noqa: ARG002
        return 6

    def get_dashboard_user_rollup(self):
        return {
            "users_total": 12,
            "users_active": 10,
            "role_user_counts": {"admin": 1},
            "profession_role_matrix": {"clinician": {"admin": 1}},
        }

    def get_dashboard_isgl_visibility(self):
        return {
            "public_total": 2,
            "private_total": 3,
            "adhoc_total": 1,
            "public_only": 1,
            "private_only": 2,
            "adhoc_only": 0,
            "public_private": 1,
            "public_adhoc": 0,
            "private_adhoc": 0,
            "public_private_adhoc": 0,
            "overlap_total": 1,
            "extra_visibility_counts": {},
        }

    def get_user_by_id(self, _id):  # noqa: ARG002
        return self.user_doc

    def resolve_active_asp_ids_for_scope(self, asp_ids, groups):  # noqa: ARG002
        return ["A2"]

    def get_dashboard_sample_rollup(self, asp_ids=None):
        if asp_ids is None:
            return {
                "total_samples": 100,
                "analysed_samples": 75,
                "pending_samples": 25,
                "sample_stats": {"all": 100},
            }
        return {"user_samples_stats": {"scoped": len(asp_ids)}}

    def get_dashboard_variant_counts(self):
        return {
            "total_variants": 2000,
            "snv": 2000,
            "small_variants": 2000,
            "total_snps": 1700,
            "fps": 100,
            "by_variant_class": {"SNV": 1700, "INDEL": 300},
        }

    def get_total_cnv_count(self):
        return 40

    def get_total_transloc_count(self):
        return 12

    def get_total_fusion_count(self):
        return 8

    def get_unique_blacklist_count(self):
        return 50

    def get_dashboard_tier_stats(self):
        return {"total": {"tier1": 10, "tier2": 5, "tier3": 3, "tier4": 1}}

    def get_dashboard_classification_stats(self):
        return {"total": {"tier1": 20, "tier2": 7, "tier3": 6, "tier4": 4}}

    def get_dashboard_top_tiered_genes(self, *, limit=15):
        assert limit == 15
        return [
            {
                "gene": "TP53",
                "total": 12,
                "tier1": 3,
                "tier2": 4,
                "tier3": 4,
                "tier4": 1,
                "nomenclatures": ["p", "c"],
            }
        ]

    def get_all_asps_unique_gene_count(self):
        return 1234

    def get_all_asp_gene_counts(self):
        return [
            {
                "asp_id": "A1",
                "display_name": "Assay 1",
                "asp_group": "hematology",
                "asp_family": "panel-dna",
                "accredited": True,
                "covered_genes_count": 42,
                "germline_genes_count": 7,
            },
            {
                "asp_id": "WGS1",
                "display_name": "TumWGS",
                "asp_group": "tumwgs",
                "asp_family": "wgs",
                "covered_genes_count": 1000,
                "germline_genes_count": 500,
            },
        ]

    def get_dashboard_isgl_association(self):
        return {"pairs": [{"isgl": "I1", "asp": "A1"}]}


def _noop_handler(**methods):
    defaults = {
        "count_users": lambda: 0,
        "count_roles": lambda is_active=None: 0,
        "count_asps": lambda is_active=None: 0,
        "count_aspcs": lambda is_active=None: 0,
        "get_dashboard_analysis_type_rollup": lambda asp_ids: [],
        "count_isgls": lambda is_active=None: 0,
        "get_dashboard_user_rollup": lambda: {},
        "get_dashboard_visibility_rollup": lambda: {},
        "user_with_id": lambda _id: {},
        "resolve_active_asp_ids_for_scope": lambda asp_ids=None, groups=None: [],
        "get_dashboard_sample_rollup": lambda asp_ids=None: {},
        "get_dashboard_variant_counts": lambda: {},
        "get_total_cnv_count": lambda: 0,
        "get_total_transloc_count": lambda: 0,
        "get_total_fusion_count": lambda: 0,
        "get_unique_blacklist_count": lambda: 0,
        "get_dashboard_tier_stats": lambda: {},
        "get_dashboard_classification_stats": lambda: {},
        "get_dashboard_top_tiered_genes": lambda limit=15: [],
        "get_all_asps_unique_gene_count": lambda: 0,
        "get_all_asp_gene_counts": lambda: {},
        "get_dashboard_assay_association_rollup": lambda: {},
    }
    defaults.update(methods)
    return SimpleNamespace(**defaults)


class _DashboardMetricsStub:
    def __init__(self, document=None) -> None:
        self.document = document
        self.writes: list[tuple[str, dict]] = []

    def get_summary_snapshot(self, *, scope_key):  # noqa: ARG002
        return self.document

    def upsert_summary_snapshot(self, *, scope_key, payload):
        self.writes.append((scope_key, payload))
        self.document = {
            "payload": payload,
            "updated_at": datetime.now(timezone.utc),
        }


def _dashboard_service(backend=None, dashboard_metrics_repository=None) -> DashboardService:
    backend = backend or _DashboardBackendStub()
    return DashboardService(
        user_repository=_noop_handler(
            count_users=backend.count_users,
            user_with_id=backend.get_user_by_id,
            get_dashboard_user_rollup=backend.get_dashboard_user_rollup,
        ),
        roles_repository=_noop_handler(count_roles=backend.count_roles),
        assay_panel_repository=_noop_handler(
            count_asps=backend.count_asps,
            resolve_active_asp_ids_for_scope=backend.resolve_active_asp_ids_for_scope,
            get_all_asps_unique_gene_count=backend.get_all_asps_unique_gene_count,
            get_all_asp_gene_counts=backend.get_all_asp_gene_counts,
        ),
        assay_configuration_repository=_noop_handler(
            count_aspcs=backend.count_aspcs,
            get_dashboard_analysis_type_rollup=backend.get_dashboard_analysis_type_rollup,
        ),
        gene_list_repository=_noop_handler(
            count_isgls=backend.count_isgls,
            get_dashboard_visibility_rollup=backend.get_dashboard_isgl_visibility,
            get_dashboard_assay_association_rollup=backend.get_dashboard_isgl_association,
        ),
        sample_repository=_noop_handler(
            get_dashboard_sample_rollup=backend.get_dashboard_sample_rollup
        ),
        variant_repository=_noop_handler(
            get_dashboard_variant_counts=backend.get_dashboard_variant_counts,
        ),
        copy_number_variant_repository=_noop_handler(
            get_total_cnv_count=backend.get_total_cnv_count
        ),
        translocation_repository=_noop_handler(
            get_total_transloc_count=backend.get_total_transloc_count
        ),
        fusion_repository=_noop_handler(get_total_fusion_count=backend.get_total_fusion_count),
        blacklist_repository=_noop_handler(
            get_unique_blacklist_count=backend.get_unique_blacklist_count
        ),
        annotation_repository=_noop_handler(
            get_dashboard_classification_stats=backend.get_dashboard_classification_stats,
            get_dashboard_top_tiered_genes=backend.get_dashboard_top_tiered_genes,
        ),
        reported_variant_repository=_noop_handler(
            get_dashboard_tier_stats=backend.get_dashboard_tier_stats
        ),
        dashboard_metrics_repository=dashboard_metrics_repository,
    )


def test_build_isgl_visibility_counts_combinations():
    service = _dashboard_service(backend=_DashboardBackendStub())
    rows = [
        {"is_public": True, "is_private": False, "adhoc": False, "is_research": True},
        {"is_public": False, "is_private": True, "adhoc": False},
        {"is_public": True, "is_private": True, "adhoc": False},
        {"is_public": False, "is_private": False, "adhoc": True},
    ]

    payload = service.build_isgl_visibility(rows)

    assert payload["public_total"] == 2
    assert payload["private_total"] == 2
    assert payload["adhoc_total"] == 1
    assert payload["public_only"] == 1
    assert payload["private_only"] == 1
    assert payload["public_private"] == 1
    assert payload["extra_visibility_counts"]["is_research"] == 1


def test_resolve_scope_assays_admin_returns_none():
    backend = _DashboardBackendStub()
    backend.user_doc = {"role": "admin", "roles": ["superuser"], "assays": [], "assay_groups": []}
    service = _dashboard_service(backend=backend)
    user = SimpleNamespace(id="u1", role="admin", roles=["admin"], asp_ids=[], asp_groups=[])

    assert service.resolve_scope_assays(user=user) is None


def test_resolve_scope_assays_returns_combined_assays():
    service = _dashboard_service(backend=_DashboardBackendStub())
    user = SimpleNamespace(
        id="u1", role="analyst", roles=["analyst"], asp_ids=["A1"], asp_groups=["G1"]
    )

    payload = service.resolve_scope_assays(user=user)

    assert payload == ["A1", "A2"]


def test_summary_payload_calculates_quality_rates(monkeypatch):
    service = _dashboard_service(backend=_DashboardBackendStub())
    user = SimpleNamespace(
        id="u1", role="admin", roles=["superuser"], asp_ids=["A1"], asp_groups=["G1"]
    )
    monkeypatch.setattr(service, "build_admin_insights", lambda: {"counts": {"users_total": 12}})
    monkeypatch.setattr(
        "api.application.dashboard.analytics.util",
        SimpleNamespace(
            dashboard=SimpleNamespace(format_asp_gene_stats=lambda rows: {"formatted": rows})
        ),
        raising=False,
    )

    payload = service.refresh_summary_payload(user=user)

    assert payload["total_samples"] == 100
    assert payload["analysed_samples"] == 75
    assert payload["variant_stats"]["blacklisted"] == 50
    assert payload["variant_stats"]["snv"] == 2000
    assert payload["variant_stats"]["cnv"] == 40
    assert payload["variant_stats"]["fusion"] == 8
    assert payload["variant_stats"]["translocation"] == 12
    assert payload["variant_stats"]["reported_findings"] == 19
    assert payload["variant_stats"]["pathogenic"] == 27
    assert payload["variant_stats"]["vus"] == 6
    assert payload["variant_stats"]["tier4"] == 4
    assert payload["variant_stats"]["reported_findings"] == 19
    assert payload["variant_stats"]["by_variant_class"]["INDEL"] == 300
    assert payload["assay_gene_stats_grouped"]["hematology"][0]["covered_genes_count"] == 42
    assert payload["assay_gene_stats_grouped"]["hematology"][0]["germline_genes_count"] == 7
    assert list(payload["panel_gene_stats_grouped"]) == ["hematology"]
    assert payload["panel_portfolio"] == {
        "active_panels": 1,
        "assay_groups": 1,
        "covered_gene_assignments": 42,
        "germline_gene_assignments": 7,
        "accredited_panels": 1,
    }
    assert payload["panel_analysis_capabilities"] == [
        {"analysis_type": "SNV", "enabled": 2, "reportable": 2},
        {"analysis_type": "CNV", "enabled": 2, "reportable": 1},
    ]
    assert payload["top_tiered_genes"][0] == {
        "gene": "TP53",
        "total": 12,
        "tier1": 3,
        "tier2": 4,
        "tier3": 4,
        "tier4": 1,
        "nomenclatures": ["p", "c"],
    }
    assert payload["quality_stats"]["analysed_rate_percent"] == 75.0
    assert payload["quality_stats"]["fp_rate_percent"] == 5.0
    assert payload["admin_insights"]["counts"]["users_total"] == 12
    assert payload["dashboard_meta"]["scope_assays"] == ["A1", "A2"]


def test_summary_payload_reads_snapshot_without_running_aggregations(monkeypatch):
    snapshot = {
        "payload": {"total_samples": 7, "dashboard_meta": {}},
        "updated_at": datetime.now(timezone.utc),
    }
    service = _dashboard_service(
        backend=_DashboardBackendStub(),
        dashboard_metrics_repository=_DashboardMetricsStub(snapshot),
    )
    monkeypatch.setattr(
        service.sample_repository,
        "get_dashboard_sample_rollup",
        lambda **_kwargs: pytest.fail("dashboard GET must not aggregate MongoDB data"),
    )
    user = SimpleNamespace(id="u1", role="admin", roles=["superuser"], asp_ids=[], asp_groups=[])

    payload = service.summary_payload(user=user)

    assert payload["total_samples"] == 7
    assert payload["dashboard_meta"]["snapshot_stale"] is False


def test_summary_payload_returns_stale_snapshot_and_rejects_missing_snapshot():
    old_snapshot = {
        "payload": {"total_samples": 7, "dashboard_meta": {}},
        "updated_at": datetime.now(timezone.utc) - timedelta(minutes=10),
        "dirty_since": datetime.now(timezone.utc),
    }
    user = SimpleNamespace(id="u1", role="admin", roles=["superuser"], asp_ids=[], asp_groups=[])
    service = _dashboard_service(
        backend=_DashboardBackendStub(),
        dashboard_metrics_repository=_DashboardMetricsStub(old_snapshot),
    )

    assert service.summary_payload(user=user)["dashboard_meta"]["snapshot_stale"] is True

    service = _dashboard_service(
        backend=_DashboardBackendStub(),
        dashboard_metrics_repository=_DashboardMetricsStub(),
    )
    with pytest.raises(DashboardSnapshotUnavailable):
        service.summary_payload(user=user)


def test_panel_gene_stats_exclude_wgs_and_wts_families():
    rows = [
        {
            "asp_id": "dna",
            "asp_group": "solid",
            "asp_family": "panel-dna",
            "covered_genes_count": 500,
        },
        {
            "asp_id": "rna",
            "asp_group": "solid",
            "asp_family": "panel-rna",
            "covered_genes_count": 160,
        },
        {"asp_id": "wgs", "asp_group": "tumwgs", "asp_family": "wgs", "covered_genes_count": 20000},
        {"asp_id": "wts", "asp_group": "wts", "asp_family": "wts", "covered_genes_count": 20000},
    ]

    grouped = format_panel_gene_stats(rows)
    summary = summarize_panel_gene_stats(rows)

    assert [row["asp_id"] for row in grouped["solid"]] == ["dna", "rna"]
    assert "tumwgs" not in grouped
    assert "wts" not in grouped
    assert summary["active_panels"] == 2
    assert summary["covered_gene_assignments"] == 660


def test_panel_asp_ids_exclude_non_panel_families():
    assert panel_asp_ids(
        [
            {"asp_id": "solid_gmsv3", "asp_family": "panel-dna"},
            {"asp_id": "tumwgs_solid", "asp_family": "wgs"},
            {"asp_id": "fusion", "asp_family": "wts"},
        ]
    ) == ["solid_gmsv3"]
