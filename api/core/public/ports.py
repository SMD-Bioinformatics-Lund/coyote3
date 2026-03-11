"""Ports for public catalog data access."""

from __future__ import annotations

from typing import Any, Protocol


class PublicCatalogRepository(Protocol):
    def get_aspc_with_id(self, aspc_id: str) -> dict[str, Any] | None: ...

    def get_asp(self, asp_id: str) -> dict[str, Any] | None: ...

    def get_asp_genes(self, asp_id: str) -> tuple[list[str], list[str]]: ...

    def get_isgl(
        self,
        isgl_id: str | None,
        *,
        is_active: bool | None = None,
        is_public: bool | None = None,
    ) -> dict[str, Any] | None: ...

    def get_hgnc_metadata_by_symbols(self, symbols: list[str]) -> list[dict[str, Any]]: ...
