"""Ports for admin workflows."""

from __future__ import annotations

from typing import Any, Protocol


class AdminSampleDeletionRepository(Protocol):
    """Define the persistence operations required for admin sample deletion."""

    def get_sample_by_id(self, sample_id: str) -> dict[str, Any] | None:
        """Return sample by id.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        ...

    def delete_sample_variants(self, sample_id: str) -> Any:
        """Delete sample variants.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            Any: The function result.
        """
        ...

    def delete_sample_cnvs(self, sample_id: str) -> Any:
        """Delete sample cnvs.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            Any: The function result.
        """
        ...

    def delete_sample_coverage(self, sample_id: str) -> Any:
        """Delete sample coverage.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            Any: The function result.
        """
        ...

    def delete_sample_panel_coverage(self, sample_id: str) -> Any:
        """Delete sample panel coverage.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            Any: The function result.
        """
        ...

    def delete_sample_translocs(self, sample_id: str) -> Any:
        """Delete sample translocs.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            Any: The function result.
        """
        ...

    def delete_sample_fusions(self, sample_id: str) -> Any:
        """Delete sample fusions.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            Any: The function result.
        """
        ...

    def delete_sample_biomarkers(self, sample_id: str) -> Any:
        """Delete sample biomarkers.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            Any: The function result.
        """
        ...

    def delete_sample(self, sample_id: str) -> Any:
        """Delete sample.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            Any: The function result.
        """
        ...
