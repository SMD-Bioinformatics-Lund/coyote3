"""Unit tests for dashboard service calculations and scope behavior."""

from __future__ import annotations

from types import SimpleNamespace

from api.services.dashboard.analytics import DashboardService


class _DashboardRepoStub:
    def __init__(self) -> None:
        self.user_doc = {"role": "analyst", "assays": ["A1"], "assay_groups": ["G1"]}

    def count_users(self):
        return 10

    def count_roles(self, is_active=None):  # noqa: ARG002
        return 3

    def count_asps(self, is_active=None):  # noqa: ARG002
        return 4

    def count_aspcs(self, is_active=None):  # noqa: ARG002
        return 5

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

    def resolve_active_asp_ids_for_scope(self, assays, groups):  # noqa: ARG002
        return ["A2"]

    def get_dashboard_sample_rollup(self, assays=None):
        if assays is None:
            return {
                "total_samples": 100,
                "analysed_samples": 75,
                "pending_samples": 25,
                "sample_stats": {"all": 100},
            }
        return {"user_samples_stats": {"scoped": len(assays)}}

    def get_dashboard_variant_counts(self):
        return {"total_variants": 2000, "total_snps": 1700, "fps": 100}

    def get_unique_variant_quality_counts(self):
        return {"unique_total_variants": 500, "unique_fp_variants": 25}

    def get_total_cnv_count(self):
        return 40

    def get_total_transloc_count(self):
        return 12

    def get_total_fusion_count(self):
        return 8

    def get_unique_blacklist_count(self):
        return 50

    def get_dashboard_tier_stats(self):
        return {"tier_1": 10}

    def get_all_asps_unique_gene_count(self):
        return 1234

    def get_all_asp_gene_counts(self):
        return [{"asp_id": "A1", "gene_count": 10}]

    def get_dashboard_isgl_association(self):
        return {"pairs": [{"isgl": "I1", "asp": "A1"}]}


def test_build_isgl_visibility_counts_combinations():
    service = DashboardService(repository=_DashboardRepoStub())
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
    repo = _DashboardRepoStub()
    repo.user_doc = {"role": "admin", "assays": [], "assay_groups": []}
    service = DashboardService(repository=repo)
    user = SimpleNamespace(id="u1", role="admin", assays=[], assay_groups=[])

    assert service.resolve_scope_assays(user=user) is None


def test_resolve_scope_assays_returns_combined_assays():
    service = DashboardService(repository=_DashboardRepoStub())
    user = SimpleNamespace(id="u1", role="analyst", assays=["A1"], assay_groups=["G1"])

    payload = service.resolve_scope_assays(user=user)

    assert payload == ["A1", "A2"]


def test_summary_payload_calculates_quality_rates(monkeypatch):
    service = DashboardService(repository=_DashboardRepoStub())
    user = SimpleNamespace(id="u1", role="admin", assays=["A1"], assay_groups=["G1"])
    monkeypatch.setattr(service, "build_admin_insights", lambda: {"counts": {"users_total": 12}})
    monkeypatch.setattr(
        "api.services.dashboard.analytics.util",
        SimpleNamespace(
            dashboard=SimpleNamespace(format_asp_gene_stats=lambda rows: {"formatted": rows})
        ),
        raising=False,
    )

    payload = service.summary_payload(user=user)

    assert payload["total_samples"] == 100
    assert payload["analysed_samples"] == 75
    assert payload["variant_stats"]["blacklisted"] == 50
    assert payload["quality_stats"]["analysed_rate_percent"] == 75.0
    assert payload["quality_stats"]["fp_rate_percent"] == 5.0
    assert payload["quality_stats"]["blacklist_rate_percent"] == 10.0
    assert payload["admin_insights"]["counts"]["users_total"] == 12
    assert payload["dashboard_meta"]["scope_assays"] == ["A1", "A2"]
