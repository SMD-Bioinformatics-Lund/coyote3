"""Service-level DNA translocation query builders."""

from __future__ import annotations

from typing import Any


def build_transloc_query(sample_id: str, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build translocation query for a sample."""
    settings = settings or {}
    return {"SAMPLE_ID": sample_id}


def translocation_genes(translocation: dict[str, Any]) -> list[str]:
    """Return normalized gene symbols carried by a translocation document."""
    gene_values: list[str] = []
    genes = translocation.get("genes")
    if isinstance(genes, list):
        for gene in genes:
            if isinstance(gene, dict):
                gene_values.append(str(gene.get("gene") or gene.get("symbol") or ""))
            elif gene:
                gene_values.append(str(gene))
    gene_values.extend(
        str(gene)
        for gene in (
            translocation.get("gene1") or translocation.get("GENE1"),
            translocation.get("gene2") or translocation.get("GENE2"),
        )
        if gene
    )

    info = translocation.get("INFO") or {}
    if isinstance(info, list):
        info = next((item for item in info if isinstance(item, dict)), {})
    if isinstance(info, dict):
        annotations: list[dict[str, Any]] = []
        mane = info.get("MANE_ANN")
        if isinstance(mane, dict):
            annotations.append(mane)
        annotations.extend(item for item in (info.get("ANN") or []) if isinstance(item, dict))
        for annotation in annotations:
            raw_names = annotation.get("Gene_Name") or annotation.get("SYMBOL") or ""
            gene_values.extend(str(raw_names).replace("::", "&").split("&"))

    return list(dict.fromkeys(value.strip().upper() for value in gene_values if str(value).strip()))


def filter_translocations_by_genes(
    translocations: list[dict[str, Any]],
    *,
    filter_genes: list[str],
    restricted: bool,
) -> list[dict[str, Any]]:
    """Apply one resolved DNA translocation gene scope."""
    if not restricted:
        return translocations
    allowed = {str(gene).strip().upper() for gene in filter_genes if str(gene).strip()}
    if not allowed:
        return []
    return [
        translocation
        for translocation in translocations
        if allowed & set(translocation_genes(translocation))
    ]
