"""Mongo-backed repository adapter for the public catalog service."""

from __future__ import annotations

from typing import Any

from api.extensions import store


class MongoPublicCatalogRepository:
    def get_aspc_with_id(self, aspc_id: str) -> dict[str, Any] | None:
        return store.aspc_handler.get_aspc_with_id(aspc_id)

    def get_asp(self, asp_id: str) -> dict[str, Any] | None:
        return store.asp_handler.get_asp(asp_id)

    def get_asp_genes(self, asp_id: str) -> tuple[list[str], list[str]]:
        genes, germline = store.asp_handler.get_asp_genes(asp_id)
        return list(genes or []), list(germline or [])

    def get_isgl(
        self,
        isgl_id: str | None,
        *,
        is_active: bool | None = None,
        is_public: bool | None = None,
    ) -> dict[str, Any] | None:
        if not isgl_id:
            return None

        kwargs: dict[str, Any] = {}
        if is_active is not None:
            kwargs["is_active"] = is_active
        if is_public is not None:
            kwargs["is_public"] = is_public
        return store.isgl_handler.get_isgl(isgl_id, **kwargs)

    def get_hgnc_metadata_by_symbols(self, symbols: list[str]) -> list[dict[str, Any]]:
        return list(store.hgnc_handler.get_metadata_by_symbols(symbols) or [])
