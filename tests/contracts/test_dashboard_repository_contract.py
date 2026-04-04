"""Repository contract tests for dashboard persistence adapters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from api.infra.repositories.dashboard_mongo import DashboardRepository


class _DashboardMetricsCollection:
    def __init__(self):
        self.docs = {}
        self.last_update = None

    def find_one(self, query, projection=None):
        _ = projection
        return self.docs.get(query["_id"])

    def update_one(self, query, update, upsert=False):
        _ = upsert
        payload = dict(update["$set"])
        self.last_update = (query, payload)
        self.docs[query["_id"]] = payload


def test_dashboard_repository_contract(monkeypatch):
    metrics = _DashboardMetricsCollection()
    now = datetime.now(timezone.utc)
    metrics.docs["dashboard_summary_v2:scope-a"] = {
        "payload": {"users": 3},
        "updated_at": now,
    }
    metrics.docs["dashboard_summary_v2:stale"] = {
        "payload": {"users": 1},
        "updated_at": now - timedelta(hours=2),
    }
    store_stub = SimpleNamespace(
        coyote_db={"dashboard_metrics": metrics},
        user_handler=SimpleNamespace(
            count_users=lambda: 12,
            get_all_users=lambda: [{"_id": "u1"}],
            get_dashboard_user_rollup=lambda: {"roles": {"admin": 1}},
            user_with_id=lambda user_id: {"_id": user_id},
        ),
        roles_handler=SimpleNamespace(count_roles=lambda is_active=None: 4),
        asp_handler=SimpleNamespace(
            count_asps=lambda is_active=None: 5,
            get_all_asps=lambda is_active=True: [{"asp_id": "wgs"}],
            resolve_active_asp_ids_for_scope=lambda assays, groups: ["asp1", "asp2"],
            get_all_asps_unique_gene_count=lambda: 99,
            get_all_asp_gene_counts=lambda: {"wgs": 99},
        ),
        aspc_handler=SimpleNamespace(count_aspcs=lambda is_active=None: 6),
        isgl_handler=SimpleNamespace(
            count_isgls=lambda is_active=None: 7,
            get_all_isgl=lambda: [{"isgl_id": "g1"}],
            get_dashboard_visibility_rollup=lambda: {"public": 2},
            get_dashboard_assay_association_rollup=lambda: {"wgs": 10},
        ),
        sample_handler=SimpleNamespace(
            get_dashboard_sample_rollup=lambda assays=None: {"total": 8}
        ),
        variant_handler=SimpleNamespace(
            get_dashboard_variant_counts=lambda: {"snv": 11},
            get_unique_total_variant_counts=lambda: 12,
            get_unique_fp_count=lambda: 2,
            get_unique_variant_quality_counts=lambda: {"pass": 9},
        ),
        cnv_handler=SimpleNamespace(get_total_cnv_count=lambda: 3),
        transloc_handler=SimpleNamespace(get_total_transloc_count=lambda: 4),
        fusion_handler=SimpleNamespace(get_total_fusion_count=lambda: 5),
        blacklist_handler=SimpleNamespace(get_unique_blacklist_count=lambda: 6),
        reported_variants_handler=SimpleNamespace(get_dashboard_tier_stats=lambda: {"tier3": 7}),
    )
    monkeypatch.setattr("api.infra.repositories.dashboard_mongo.store", store_stub)

    repo = DashboardRepository()

    assert repo.read_dashboard_summary_snapshot(scope_key="scope-a", max_age_seconds=300) == {
        "users": 3
    }
    assert repo.read_dashboard_summary_snapshot(scope_key="stale", max_age_seconds=300) is None

    repo.write_dashboard_summary_snapshot(scope_key="scope-b", payload={"users": 10})
    assert metrics.last_update[0]["_id"] == "dashboard_summary_v2:scope-b"
    assert metrics.last_update[1]["payload"] == {"users": 10}

    assert repo.count_users() == 12
    assert repo.count_roles() == 4
    assert repo.count_asps() == 5
    assert repo.count_aspcs() == 6
    assert repo.count_isgls() == 7
    assert repo.get_all_isgl() == [{"isgl_id": "g1"}]
    assert repo.get_all_users() == [{"_id": "u1"}]
    assert repo.get_dashboard_user_rollup() == {"roles": {"admin": 1}}
    assert repo.get_dashboard_isgl_visibility() == {"public": 2}
    assert repo.get_dashboard_isgl_association() == {"wgs": 10}
    assert repo.get_user_by_id("u1") == {"_id": "u1"}
    assert repo.get_all_active_asps() == [{"asp_id": "wgs"}]
    assert repo.resolve_active_asp_ids_for_scope(["WGS"], ["dna"]) == ["asp1", "asp2"]
    assert repo.get_dashboard_sample_rollup(["WGS"]) == {"total": 8}
    assert repo.get_dashboard_variant_counts() == {"snv": 11}
    assert repo.get_unique_total_variant_count() == 12
    assert repo.get_unique_fp_count() == 2
    assert repo.get_unique_variant_quality_counts() == {"pass": 9}
    assert repo.get_total_cnv_count() == 3
    assert repo.get_total_transloc_count() == 4
    assert repo.get_total_fusion_count() == 5
    assert repo.get_unique_blacklist_count() == 6
    assert repo.get_dashboard_tier_stats() == {"tier3": 7}
    assert repo.get_all_asps_unique_gene_count() == 99
    assert repo.get_all_asp_gene_counts() == {"wgs": 99}
