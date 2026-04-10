"""Unit tests for dashboard service calculations and scope behavior."""

from __future__ import annotations

from types import SimpleNamespace

from api.services.dashboard.analytics import DashboardService


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


def _noop_handler(**methods):
    defaults = {
        "count_users": lambda: 0,
        "count_roles": lambda is_active=None: 0,
        "count_asps": lambda is_active=None: 0,
        "count_aspcs": lambda is_active=None: 0,
        "count_isgls": lambda is_active=None: 0,
        "get_dashboard_user_rollup": lambda: {},
        "get_dashboard_visibility_rollup": lambda: {},
        "user_with_id": lambda _id: {},
        "resolve_active_asp_ids_for_scope": lambda assays=None, groups=None: [],
        "get_dashboard_sample_rollup": lambda assays=None: {},
        "get_dashboard_variant_counts": lambda: {},
        "get_unique_variant_quality_counts": lambda: {},
        "get_total_cnv_count": lambda: 0,
        "get_total_transloc_count": lambda: 0,
        "get_total_fusion_count": lambda: 0,
        "get_unique_blacklist_count": lambda: 0,
        "get_dashboard_tier_stats": lambda: {},
        "get_all_asps_unique_gene_count": lambda: 0,
        "get_all_asp_gene_counts": lambda: {},
        "get_dashboard_assay_association_rollup": lambda: {},
    }
    defaults.update(methods)
    return SimpleNamespace(**defaults)


def _dashboard_service(backend=None) -> DashboardService:
    backend = backend or _DashboardBackendStub()
    return DashboardService(
        user_handler=_noop_handler(
            count_users=backend.count_users,
            user_with_id=backend.get_user_by_id,
            get_dashboard_user_rollup=backend.get_dashboard_user_rollup,
        ),
        roles_handler=_noop_handler(count_roles=backend.count_roles),
        assay_panel_handler=_noop_handler(
            count_asps=backend.count_asps,
            resolve_active_asp_ids_for_scope=backend.resolve_active_asp_ids_for_scope,
            get_all_asps_unique_gene_count=backend.get_all_asps_unique_gene_count,
            get_all_asp_gene_counts=backend.get_all_asp_gene_counts,
        ),
        assay_configuration_handler=_noop_handler(count_aspcs=backend.count_aspcs),
        gene_list_handler=_noop_handler(
            count_isgls=backend.count_isgls,
            get_dashboard_visibility_rollup=backend.get_dashboard_isgl_visibility,
            get_dashboard_assay_association_rollup=backend.get_dashboard_isgl_association,
        ),
        sample_handler=_noop_handler(
            get_dashboard_sample_rollup=backend.get_dashboard_sample_rollup
        ),
        variant_handler=_noop_handler(
            get_dashboard_variant_counts=backend.get_dashboard_variant_counts,
            get_unique_variant_quality_counts=backend.get_unique_variant_quality_counts,
        ),
        copy_number_variant_handler=_noop_handler(get_total_cnv_count=backend.get_total_cnv_count),
        translocation_handler=_noop_handler(
            get_total_transloc_count=backend.get_total_transloc_count
        ),
        fusion_handler=_noop_handler(get_total_fusion_count=backend.get_total_fusion_count),
        blacklist_handler=_noop_handler(
            get_unique_blacklist_count=backend.get_unique_blacklist_count
        ),
        reported_variant_handler=_noop_handler(
            get_dashboard_tier_stats=backend.get_dashboard_tier_stats
        ),
        coyote_db=None,
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
    user = SimpleNamespace(id="u1", role="admin", roles=["admin"], assays=[], assay_groups=[])

    assert service.resolve_scope_assays(user=user) is None


def test_resolve_scope_assays_returns_combined_assays():
    service = _dashboard_service(backend=_DashboardBackendStub())
    user = SimpleNamespace(
        id="u1", role="analyst", roles=["analyst"], assays=["A1"], assay_groups=["G1"]
    )

    payload = service.resolve_scope_assays(user=user)

    assert payload == ["A1", "A2"]


def test_summary_payload_calculates_quality_rates(monkeypatch):
    service = _dashboard_service(backend=_DashboardBackendStub())
    user = SimpleNamespace(
        id="u1", role="admin", roles=["superuser"], assays=["A1"], assay_groups=["G1"]
    )
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
