"""Ports for coverage workflows."""

from __future__ import annotations

from typing import Protocol


class CoverageRepository(Protocol):
    """Define the persistence operations required by coverage workflows."""

    def is_gene_blacklisted(self, gene: str, sample_group: str) -> bool:
        """Return whether gene blacklisted is true.

        Args:
            gene (str): Value for ``gene``.
            sample_group (str): Value for ``sample_group``.

        Returns:
            bool: The function result.
        """
        ...

    def is_region_blacklisted(
        self,
        gene: str,
        region: str,
        region_id: str,
        sample_group: str,
    ) -> bool:
        """Return whether region blacklisted is true.

        Args:
            gene (str): Value for ``gene``.
            region (str): Value for ``region``.
            region_id (str): Value for ``region_id``.
            sample_group (str): Value for ``sample_group``.

        Returns:
            bool: The function result.
        """
        ...

