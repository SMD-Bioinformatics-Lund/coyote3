"""Mongo repository adapter for sample mutation endpoints."""

from __future__ import annotations

from api.extensions import store


class MongoSamplesRepository:
    """Provide mongo samples persistence operations."""

    def add_sample_comment(self, sample_id: str, doc: dict) -> None:
        """Handle add sample comment.

        Args:
            sample_id (str): Value for ``sample_id``.
            doc (dict): Value for ``doc``.

        Returns:
            None.
        """
        store.sample_handler.add_sample_comment(sample_id, doc)

    def hide_sample_comment(self, sample_id: str, comment_id: str) -> None:
        """Handle hide sample comment.

        Args:
            sample_id (str): Value for ``sample_id``.
            comment_id (str): Value for ``comment_id``.

        Returns:
            None.
        """
        store.sample_handler.hide_sample_comment(sample_id, comment_id)

    def unhide_sample_comment(self, sample_id: str, comment_id: str) -> None:
        """Handle unhide sample comment.

        Args:
            sample_id (str): Value for ``sample_id``.
            comment_id (str): Value for ``comment_id``.

        Returns:
            None.
        """
        store.sample_handler.unhide_sample_comment(sample_id, comment_id)

    def update_sample_filters(self, sample_id: str, filters: dict) -> None:
        """Update sample filters.

        Args:
            sample_id (str): Value for ``sample_id``.
            filters (dict): Value for ``filters``.

        Returns:
            None.
        """
        store.sample_handler.update_sample_filters(sample_id, filters)

    def reset_sample_settings(self, sample_id: str, filters: dict) -> None:
        """Reset sample settings.

        Args:
            sample_id (str): Value for ``sample_id``.
            filters (dict): Value for ``filters``.

        Returns:
            None.
        """
        store.sample_handler.reset_sample_settings(sample_id, filters)

    def blacklist_coord(self, gene: str, coord: str, region: str, assay_group: str) -> None:
        """Handle blacklist coord.

        Args:
            gene (str): Value for ``gene``.
            coord (str): Value for ``coord``.
            region (str): Value for ``region``.
            assay_group (str): Value for ``assay_group``.

        Returns:
            None.
        """
        store.groupcov_handler.blacklist_coord(gene, coord, region, assay_group)

    def blacklist_gene(self, gene: str, assay_group: str) -> None:
        """Handle blacklist gene.

        Args:
            gene (str): Value for ``gene``.
            assay_group (str): Value for ``assay_group``.

        Returns:
            None.
        """
        store.groupcov_handler.blacklist_gene(gene, assay_group)

    def remove_blacklist(self, obj_id: str) -> None:
        """Remove blacklist.

        Args:
            obj_id (str): Value for ``obj_id``.

        Returns:
            None.
        """
        store.groupcov_handler.remove_blacklist(obj_id)
