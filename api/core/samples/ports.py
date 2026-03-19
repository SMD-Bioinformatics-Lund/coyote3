"""Repository port for sample mutation endpoints."""

from __future__ import annotations

from typing import Protocol


class SamplesRepository(Protocol):
    """Define the persistence operations required by sample mutation routes."""

    def add_sample_comment(self, sample_id: str, doc: dict) -> None:
        """Add sample comment.

        Args:
            sample_id (str): Value for ``sample_id``.
            doc (dict): Value for ``doc``.

        Returns:
            None.
        """
        ...

    def hide_sample_comment(self, sample_id: str, comment_id: str) -> None:
        """Hide sample comment.

        Args:
            sample_id (str): Value for ``sample_id``.
            comment_id (str): Value for ``comment_id``.

        Returns:
            None.
        """
        ...

    def unhide_sample_comment(self, sample_id: str, comment_id: str) -> None:
        """Unhide sample comment.

        Args:
            sample_id (str): Value for ``sample_id``.
            comment_id (str): Value for ``comment_id``.

        Returns:
            None.
        """
        ...

    def update_sample_filters(self, sample_id: str, filters: dict) -> None:
        """Update sample filters.

        Args:
            sample_id (str): Value for ``sample_id``.
            filters (dict): Value for ``filters``.

        Returns:
            None.
        """
        ...

    def reset_sample_settings(self, sample_id: str, filters: dict) -> None:
        """Handle reset sample settings.

        Args:
            sample_id (str): Value for ``sample_id``.
            filters (dict): Value for ``filters``.

        Returns:
            None.
        """
        ...

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
        ...

    def blacklist_gene(self, gene: str, assay_group: str) -> None:
        """Handle blacklist gene.

        Args:
            gene (str): Value for ``gene``.
            assay_group (str): Value for ``assay_group``.

        Returns:
            None.
        """
        ...

    def remove_blacklist(self, obj_id: str) -> None:
        """Remove blacklist.

        Args:
            obj_id (str): Value for ``obj_id``.

        Returns:
            None.
        """
        ...
