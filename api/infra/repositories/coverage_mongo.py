"""Mongo-backed repository adapter for coverage processing workflow."""

from __future__ import annotations

from api.extensions import store


class MongoCoverageRepository:
    """Provide mongo coverage persistence operations.
    """
    def is_gene_blacklisted(self, gene: str, sample_group: str) -> bool:
        """Return whether gene blacklisted is true.

        Args:
            gene (str): Value for ``gene``.
            sample_group (str): Value for ``sample_group``.

        Returns:
            bool: The function result.
        """
        return bool(store.groupcov_handler.is_gene_blacklisted(gene, sample_group))

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
        return bool(
            store.groupcov_handler.is_region_blacklisted(gene, region, region_id, sample_group)
        )

    def get_regions_per_group(self, group: str) -> list[dict]:
        """Return all blacklist entries for an assay group."""
        return list(store.groupcov_handler.get_regions_per_group(group) or [])
