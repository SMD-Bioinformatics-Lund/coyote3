"""Mongo repository adapter for dashboard read models."""

from __future__ import annotations


from api.extensions import store


class MongoDashboardRepository:
    def count_users(self) -> int:
        return int(store.user_handler.count_users())

    def count_roles(self, is_active: bool | None = None) -> int:
        return int(store.roles_handler.count_roles(is_active=is_active))

    def count_asps(self, is_active: bool | None = None) -> int:
        return int(store.asp_handler.count_asps(is_active=is_active))

    def count_aspcs(self, is_active: bool | None = None) -> int:
        return int(store.aspc_handler.count_aspcs(is_active=is_active))

    def count_isgls(self) -> int:
        return int(store.isgl_handler.count_isgls())

    def get_all_isgl(self) -> list[dict]:
        return list(store.isgl_handler.get_all_isgl() or [])

    def get_all_users(self) -> list[dict]:
        return list(store.user_handler.get_all_users() or [])

    def get_user_by_id(self, user_id: str) -> dict | None:
        return store.user_handler.user_with_id(str(user_id))

    def get_all_active_asps(self) -> list[dict]:
        return list(store.asp_handler.get_all_asps(is_active=True) or [])

    def get_dashboard_sample_rollup(self, assays: list[str] | None) -> dict:
        return store.sample_handler.get_dashboard_sample_rollup(assays=assays)

    def get_dashboard_variant_counts(self) -> dict:
        return store.variant_handler.get_dashboard_variant_counts()

    def get_total_cnv_count(self) -> int:
        return int(store.cnv_handler.get_total_cnv_count())

    def get_total_transloc_count(self) -> int:
        return int(store.transloc_handler.get_total_transloc_count())

    def get_total_fusion_count(self) -> int:
        return int(store.fusion_handler.get_total_fusion_count())

    def get_unique_blacklist_count(self) -> int:
        return int(store.blacklist_handler.get_unique_blacklist_count())

    def get_dashboard_tier_stats(self) -> dict:
        return store.reported_variants_handler.get_dashboard_tier_stats()

    def get_all_asps_unique_gene_count(self) -> int:
        return int(store.asp_handler.get_all_asps_unique_gene_count())

    def get_all_asp_gene_counts(self) -> dict:
        return store.asp_handler.get_all_asp_gene_counts()
