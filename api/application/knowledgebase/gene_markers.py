"""Shared knowledgebase gene-marker enrichment for finding lists."""

from __future__ import annotations

from typing import Any


def cosmic_cancer_gene_map(repository: Any, genes: list[str]) -> dict[str, dict[str, Any]]:
    """Return page-bounded COSMIC Cancer Gene Census records keyed by symbol."""
    getter = getattr(repository, "get_cancer_gene_census_records", None)
    if not callable(getter) or not genes:
        return {}
    return dict(getter(genes) or {})
