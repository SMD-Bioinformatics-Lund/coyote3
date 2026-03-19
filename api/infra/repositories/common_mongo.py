"""Mongo repository adapter for common read/search endpoints."""

from __future__ import annotations

from api.extensions import store


class MongoCommonRepository:
    """Provide mongo common persistence operations."""

    def get_hgnc_metadata_by_id(self, hgnc_id: str) -> dict | None:
        """Return hgnc metadata by id.

        Args:
            hgnc_id (str): Value for ``hgnc_id``.

        Returns:
            dict | None: The function result.
        """
        return store.hgnc_handler.get_metadata_by_hgnc_id(hgnc_id=hgnc_id)

    def get_hgnc_metadata_by_symbol(self, symbol: str) -> dict | None:
        """Return hgnc metadata by symbol.

        Args:
            symbol (str): Value for ``symbol``.

        Returns:
            dict | None: The function result.
        """
        return store.hgnc_handler.get_metadata_by_symbol(symbol=symbol)

    def get_variant(self, variant_id: str) -> dict | None:
        """Return variant.

        Args:
            variant_id (str): Value for ``variant_id``.

        Returns:
            dict | None: The function result.
        """
        return store.variant_handler.get_variant(variant_id)

    def list_reported_variants(self, query: dict) -> list[dict]:
        """List reported variants.

        Args:
            query (dict): Value for ``query``.

        Returns:
            list[dict]: The function result.
        """
        return list(store.reported_variants_handler.list_reported_variants(query) or [])

    def get_all_asp_groups(self) -> list[str]:
        """Return all asp groups.

        Returns:
            list[str]: The function result.
        """
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
        """Handle find variants by search string.

        Args:
            search_str (str | None): Value for ``search_str``.
            search_mode (str): Value for ``search_mode``.
            include_annotation_text (bool): Value for ``include_annotation_text``.
            assays (list[str] | None): Value for ``assays``.
            limit (int | None): Value for ``limit``.

        Returns:
            list[dict]: The function result.
        """
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
        """Return tier stats by search.

        Args:
            search_str (str | None): Value for ``search_str``.
            search_mode (str): Value for ``search_mode``.
            include_annotation_text (bool): Value for ``include_annotation_text``.
            assays (list[str] | None): Value for ``assays``.

        Returns:
            dict: The function result.
        """
        return store.annotation_handler.get_tier_stats_by_search(
            search_str=search_str,
            search_mode=search_mode,
            include_annotation_text=include_annotation_text,
            assays=assays,
        )

    def get_sample_by_oid(self, sample_oid: str) -> dict | None:
        """Return sample by oid.

        Args:
            sample_oid (str): Value for ``sample_oid``.

        Returns:
            dict | None: The function result.
        """
        return store.sample_handler.get_sample_by_oid(sample_oid)

    def get_annotation_text_by_oid(self, annotation_text_oid: str) -> str | None:
        """Return annotation text by oid.

        Args:
            annotation_text_oid (str): Value for ``annotation_text_oid``.

        Returns:
            str | None: The function result.
        """
        return store.annotation_handler.get_annotation_text_by_oid(annotation_text_oid)
