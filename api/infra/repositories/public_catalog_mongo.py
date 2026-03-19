"""Mongo-backed repository adapter for the public catalog service."""

from __future__ import annotations

from typing import Any

from api.extensions import store


class MongoPublicCatalogRepository:
    """Provide mongo public catalog persistence operations."""

    def get_aspc_with_id(self, aspc_id: str) -> dict[str, Any] | None:
        """Return aspc with id.

        Args:
            aspc_id (str): Value for ``aspc_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return store.aspc_handler.get_aspc_with_id(aspc_id)

    def get_asp(self, asp_id: str) -> dict[str, Any] | None:
        """Return asp.

        Args:
            asp_id (str): Value for ``asp_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return store.asp_handler.get_asp(asp_id)

    def get_asp_genes(self, asp_id: str) -> tuple[list[str], list[str]]:
        """Return asp genes.

        Args:
            asp_id (str): Value for ``asp_id``.

        Returns:
            tuple[list[str], list[str]]: The function result.
        """
        genes, germline = store.asp_handler.get_asp_genes(asp_id)
        return list(genes or []), list(germline or [])

    def get_isgl(
        self,
        isgl_id: str | None,
        *,
        is_active: bool | None = None,
        is_public: bool | None = None,
    ) -> dict[str, Any] | None:
        """Return isgl.

        Args:
            isgl_id (str | None): Value for ``isgl_id``.
            is_active (bool | None): Value for ``is_active``.
            is_public (bool | None): Value for ``is_public``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        if not isgl_id:
            return None

        kwargs: dict[str, Any] = {}
        if is_active is not None:
            kwargs["is_active"] = is_active
        if is_public is not None:
            kwargs["is_public"] = is_public
        return store.isgl_handler.get_isgl(isgl_id, **kwargs)

    def get_hgnc_metadata_by_symbols(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Return hgnc metadata by symbols.

        Args:
            symbols (list[str]): Value for ``symbols``.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        return list(store.hgnc_handler.get_metadata_by_symbols(symbols) or [])
