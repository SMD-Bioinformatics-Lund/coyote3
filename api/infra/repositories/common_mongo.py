"""Mongo repository adapter for common read/search endpoints."""

from __future__ import annotations

from api.extensions import store


class MongoCommonRepository:
    def get_hgnc_metadata_by_id(self, hgnc_id: str) -> dict | None:
        return store.hgnc_handler.get_metadata_by_hgnc_id(hgnc_id=hgnc_id)

    def get_hgnc_metadata_by_symbol(self, symbol: str) -> dict | None:
        return store.hgnc_handler.get_metadata_by_symbol(symbol=symbol)

    def get_variant(self, variant_id: str) -> dict | None:
        return store.variant_handler.get_variant(variant_id)

    def list_reported_variants(self, query: dict) -> list[dict]:
        return list(store.reported_variants_handler.list_reported_variants(query) or [])

    def get_all_asp_groups(self) -> list[str]:
        return list(store.asp_handler.get_all_asp_groups() or [])

    def find_variants_by_search_string(
        self,
        *,
        search_str: str | None,
        search_mode: str,
        include_annotation_text: bool,
        assays: list[str] | None,
        limit: int | None,
    ) -> list[dict]:
        return list(
            store.annotation_handler.find_variants_by_search_string(
                search_str=search_str,
                search_mode=search_mode,
                include_annotation_text=include_annotation_text,
                assays=assays,
                limit=limit,
            )
            or []
        )

    def get_tier_stats_by_search(
        self,
        *,
        search_str: str | None,
        search_mode: str,
        include_annotation_text: bool,
        assays: list[str] | None,
    ) -> dict:
        return store.annotation_handler.get_tier_stats_by_search(
            search_str=search_str,
            search_mode=search_mode,
            include_annotation_text=include_annotation_text,
            assays=assays,
        )

    def get_sample_by_oid(self, sample_oid: str) -> dict | None:
        return store.sample_handler.get_sample_by_oid(sample_oid)

    def get_annotation_text_by_oid(self, annotation_text_oid: str) -> str | None:
        return store.annotation_handler.get_annotation_text_by_oid(annotation_text_oid)
