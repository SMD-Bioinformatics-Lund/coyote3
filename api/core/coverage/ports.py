"""Ports for coverage workflows."""

from __future__ import annotations

from typing import Protocol


class CoverageRepository(Protocol):
    def is_gene_blacklisted(self, gene: str, sample_group: str) -> bool: ...

    def is_region_blacklisted(
        self,
        gene: str,
        region: str,
        region_id: str,
        sample_group: str,
    ) -> bool: ...

