"""Mongo-backed repository adapter for coverage processing workflow."""

from __future__ import annotations

from api.extensions import store


class MongoCoverageRepository:
    def is_gene_blacklisted(self, gene: str, sample_group: str) -> bool:
        return bool(store.groupcov_handler.is_gene_blacklisted(gene, sample_group))

    def is_region_blacklisted(
        self,
        gene: str,
        region: str,
        region_id: str,
        sample_group: str,
    ) -> bool:
        return bool(
            store.groupcov_handler.is_region_blacklisted(gene, region, region_id, sample_group)
        )

