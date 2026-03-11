"""Mongo repository adapter for coverage read endpoints."""

from __future__ import annotations

from api.extensions import store


class MongoCoverageRouteRepository:
    def get_aspc_no_meta(self, assay: str, profile: str) -> dict | None:
        return store.aspc_handler.get_aspc_no_meta(assay, profile)

    def get_asp(self, asp_name: str) -> dict | None:
        return store.asp_handler.get_asp(asp_name=asp_name)

    def get_isgl_by_ids(self, ids: list[str]) -> dict:
        return store.isgl_handler.get_isgl_by_ids(ids)

    def get_sample_coverage(self, sample_id: str) -> dict | None:
        return store.coverage2_handler.get_sample_coverage(sample_id)

    def get_regions_per_group(self, group: str) -> list[dict]:
        return list(store.groupcov_handler.get_regions_per_group(group) or [])
