"""Mongo repository adapter for home/sample read + settings flows."""

from __future__ import annotations

from api.extensions import store


class MongoHomeRepository:
    def get_samples(
        self,
        *,
        user_assays: list,
        user_envs: list,
        status: str,
        report: bool,
        search_str: str,
        limit: int | None,
        offset: int,
        use_cache: bool,
        reload: bool,
    ) -> list[dict]:
        return list(
            store.sample_handler.get_samples(
                user_assays=user_assays,
                user_envs=user_envs,
                status=status,
                search_str=search_str,
                report=report,
                limit=limit,
                offset=offset,
                use_cache=use_cache,
                reload=reload,
            )
            or []
        )

    def get_isgl_by_asp(self, **query) -> list[dict]:
        return list(store.isgl_handler.get_isgl_by_asp(**query) or [])

    def get_isgl_by_ids(self, ids: list[str]) -> dict:
        return store.isgl_handler.get_isgl_by_ids(ids)

    def get_asp(self, assay: str) -> dict:
        return store.asp_handler.get_asp(assay)

    def get_asp_genes(self, assay: str) -> tuple[list, list]:
        return store.asp_handler.get_asp_genes(assay)

    def reset_sample_settings(self, sample_id: str, filters: dict) -> None:
        store.sample_handler.reset_sample_settings(sample_id, filters)

    def get_sample(self, sample_id: str) -> dict | None:
        return store.sample_handler.get_sample(sample_id)

    def get_variant_stats(self, sample_id: str, genes: list[str] | None = None) -> dict:
        if genes is None:
            return store.variant_handler.get_variant_stats(sample_id)
        return store.variant_handler.get_variant_stats(sample_id, genes=genes)

    def update_sample_filters(self, sample_id: str, filters: dict) -> None:
        store.sample_handler.update_sample_filters(sample_id, filters)

    def get_report(self, sample_id: str, report_id: str) -> dict:
        return store.sample_handler.get_report(sample_id, report_id)
