"""Repository port for common read/search endpoints."""

from __future__ import annotations

from typing import Protocol


class CommonRepository(Protocol):
    def get_hgnc_metadata_by_id(self, hgnc_id: str) -> dict | None: ...
    def get_hgnc_metadata_by_symbol(self, symbol: str) -> dict | None: ...
    def get_variant(self, variant_id: str) -> dict | None: ...
    def list_reported_variants(self, query: dict) -> list[dict]: ...
    def get_all_asp_groups(self) -> list[str]: ...
    def find_variants_by_search_string(
        self,
        *,
        search_str: str | None,
        search_mode: str,
        include_annotation_text: bool,
        assays: list[str] | None,
        limit: int | None,
    ) -> list[dict]: ...
    def get_tier_stats_by_search(
        self,
        *,
        search_str: str | None,
        search_mode: str,
        include_annotation_text: bool,
        assays: list[str] | None,
    ) -> dict: ...
    def get_sample_by_oid(self, sample_oid: str) -> dict | None: ...
    def get_annotation_text_by_oid(self, annotation_text_oid: str) -> str | None: ...
