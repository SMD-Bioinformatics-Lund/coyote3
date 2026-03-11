"""Mongo repository adapter for sample mutation endpoints."""

from __future__ import annotations

from api.extensions import store


class MongoSamplesRepository:
    def add_sample_comment(self, sample_id: str, doc: dict) -> None:
        store.sample_handler.add_sample_comment(sample_id, doc)

    def hide_sample_comment(self, sample_id: str, comment_id: str) -> None:
        store.sample_handler.hide_sample_comment(sample_id, comment_id)

    def unhide_sample_comment(self, sample_id: str, comment_id: str) -> None:
        store.sample_handler.unhide_sample_comment(sample_id, comment_id)

    def update_sample_filters(self, sample_id: str, filters: dict) -> None:
        store.sample_handler.update_sample_filters(sample_id, filters)

    def reset_sample_settings(self, sample_id: str, filters: dict) -> None:
        store.sample_handler.reset_sample_settings(sample_id, filters)

    def blacklist_coord(self, gene: str, coord: str, region: str, assay_group: str) -> None:
        store.groupcov_handler.blacklist_coord(gene, coord, region, assay_group)

    def blacklist_gene(self, gene: str, assay_group: str) -> None:
        store.groupcov_handler.blacklist_gene(gene, assay_group)

    def remove_blacklist(self, obj_id: str) -> None:
        store.groupcov_handler.remove_blacklist(obj_id)
