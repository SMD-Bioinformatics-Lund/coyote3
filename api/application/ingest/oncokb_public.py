"""HGNC-backed public OncoKB gene-cache refresh helpers."""

from __future__ import annotations

from typing import Any

from api.infra.knowledgebase.public_oncokb import PublicOncoKbClient


def _extract_oncokb_gene_symbol(record: dict[str, Any]) -> str:
    """Extract a gene symbol from public OncoKB cancer-gene payload variants."""
    gene = record.get("gene")
    if isinstance(gene, dict):
        return str(gene.get("hugoSymbol") or gene.get("symbol") or "").strip()
    for key in ("hugoSymbol", "hugo_symbol", "gene", "symbol"):
        value = record.get(key)
        if value:
            return str(value).strip()
    return ""


def _hgnc_doc_for_symbol(
    symbol: str,
    hgnc_collection: Any | None,
    *,
    symbol_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return HGNC metadata by approved, previous, or alias symbol."""
    normalized = str(symbol or "").strip().upper()
    if symbol_index is not None:
        return symbol_index.get(normalized)
    if hgnc_collection is not None and hasattr(hgnc_collection, "get_metadata_by_symbol_or_alias"):
        return hgnc_collection.get_metadata_by_symbol_or_alias(symbol)
    if hgnc_collection is None or not hasattr(hgnc_collection, "find_one"):
        return None
    return hgnc_collection.find_one(
        {
            "$or": [
                {"hgnc_symbol": symbol},
                {"prev_symbol": symbol},
                {"alias_symbol": symbol},
            ]
        },
        {
            "_id": 1,
            "hgnc_id": 1,
            "hgnc_symbol": 1,
            "prev_symbol": 1,
            "alias_symbol": 1,
        },
    )


def _hgnc_doc_for_record(
    record: dict[str, Any],
    hgnc_collection: Any | None,
    *,
    symbol_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Resolve an OncoKB record through any of its published gene symbols."""
    for symbol in sorted(_record_symbols(record)):
        if hgnc_doc := _hgnc_doc_for_symbol(
            symbol,
            hgnc_collection,
            symbol_index=symbol_index,
        ):
            return hgnc_doc
    return None


def _normalized_symbols(values: Any) -> set[str]:
    """Normalize panel and OncoKB symbols for case-insensitive matching."""
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return set()
    return {str(value).strip().upper() for value in values if str(value or "").strip()}


def _record_symbols(record: dict[str, Any]) -> set[str]:
    """Return every public symbol that can identify an OncoKB gene record."""
    return _normalized_symbols(
        [
            _extract_oncokb_gene_symbol(record),
            *list(record.get("geneAliases") or []),
            *list(record.get("aliases") or []),
        ]
    )


def _hgnc_symbol_index(hgnc_repository: Any | None) -> tuple[dict[str, dict[str, Any]], int]:
    """Index the local HGNC catalogue by every supported gene symbol."""
    if hgnc_repository is None or not hasattr(hgnc_repository, "iter_gene_metadata"):
        return {}, 0
    records = list(hgnc_repository.iter_gene_metadata() or [])
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        for symbol in _normalized_symbols(
            [
                record.get("hgnc_symbol"),
                *(record.get("prev_symbol") or []),
                *(record.get("alias_symbol") or []),
            ]
        ):
            index.setdefault(symbol, record)
    return index, len(records)


def refresh_public_oncokb_gene_cache(
    *,
    client: PublicOncoKbClient,
    cache_repository: Any,
    hgnc_repository: Any | None = None,
) -> dict[str, int]:
    """Refresh public OncoKB gene data against the complete local HGNC catalogue.

    The public endpoints are fetched once per refresh. Their records are kept
    only when a current HGNC record resolves the reported symbol, previous
    symbol, or alias. This is shared reference maintenance, independent of
    assay-panel administration and sample ingestion.
    """
    hgnc_index, hgnc_gene_records = _hgnc_symbol_index(hgnc_repository)
    result = {
        "hgnc_gene_records": hgnc_gene_records,
        "hgnc_symbols_indexed": len(hgnc_index),
        "cancer_records_fetched": 0,
        "cancer_records_matched": 0,
        "cancer_genes_upserted": 0,
        "cancer_genes_removed": 0,
        "curated_records_fetched": 0,
        "curated_records_matched": 0,
        "curated_genes_upserted": 0,
        "curated_genes_removed": 0,
    }
    if not hgnc_index:
        raise RuntimeError(
            "The HGNC catalogue is empty; public OncoKB refresh requires local HGNC gene metadata."
        )

    source = "public.api.oncokb.org"
    hgnc_symbols = set(hgnc_index)
    cancer_records = client.cancer_gene_list()
    result["cancer_records_fetched"] = len(cancer_records)
    curated_records = client.all_curated_genes(include_evidence=True)
    result["curated_records_fetched"] = len(curated_records)

    matching_cancer_records = [
        record for record in cancer_records if _record_symbols(record) & hgnc_symbols
    ]
    result["cancer_records_matched"] = len(matching_cancer_records)
    cancer_docs = [
        document
        for record in matching_cancer_records
        if (
            document := _public_gene_marker_from_cancer_gene(
                record=record,
                hgnc_collection=hgnc_repository,
                hgnc_symbol_index=hgnc_index,
                source=source,
            )
        )
    ]
    matching_curated_records = [
        record for record in curated_records if _record_symbols(record) & hgnc_symbols
    ]
    result["curated_records_matched"] = len(matching_curated_records)
    curated_docs = [
        document
        for record in matching_curated_records
        if (
            document := _public_gene_summary_from_curated_gene(
                record=record,
                hgnc_collection=hgnc_repository,
                hgnc_symbol_index=hgnc_index,
                source=source,
            )
        )
    ]

    # Fetch and normalize both public catalogues before mutating either local cache.
    result["cancer_genes_upserted"] = cache_repository.upsert_cancer_gene_markers(cancer_docs)
    result["cancer_genes_removed"] = cache_repository.remove_cancer_gene_markers_not_in(
        {str(document["gene"]) for document in cancer_docs}
    )
    result["curated_genes_upserted"] = cache_repository.upsert_gene_markers(curated_docs)
    result["curated_genes_removed"] = cache_repository.remove_gene_markers_not_in(
        {str(document["gene"]) for document in curated_docs}
    )
    return result


def _public_gene_marker_from_cancer_gene(
    *,
    record: dict[str, Any],
    hgnc_collection: Any | None,
    hgnc_symbol_index: dict[str, dict[str, Any]] | None = None,
    source: str,
) -> dict[str, Any] | None:
    """Build a normalized public cancer-gene marker from one OncoKB record."""
    symbol = _extract_oncokb_gene_symbol(record)
    if not symbol:
        return None
    hgnc_doc = _hgnc_doc_for_record(
        record,
        hgnc_collection,
        symbol_index=hgnc_symbol_index,
    )
    approved_symbol = str((hgnc_doc or {}).get("hgnc_symbol") or symbol).strip()
    return {
        "gene": approved_symbol,
        "source": source,
        "public_api": True,
        "therapeutic_data_included": False,
        "data_version": record.get("dataVersion") or record.get("version"),
        "hgnc_id": (hgnc_doc or {}).get("hgnc_id") or (hgnc_doc or {}).get("_id"),
        "previous_symbols": (hgnc_doc or {}).get("prev_symbol") or [],
        "alias_symbols": (hgnc_doc or {}).get("alias_symbol") or record.get("geneAliases") or [],
        "entrez_gene_id": record.get("entrezGeneId"),
        "gene_type": record.get("geneType"),
        "occurrence_count": record.get("occurrenceCount"),
        "oncokb_annotated": record.get("oncokbAnnotated"),
        "sanger_cgc": record.get("sangerCGC"),
        "vogelstein": record.get("vogelstein"),
        "foundation": record.get("foundation"),
        "foundation_heme": record.get("foundationHeme"),
        "msk_impact": record.get("mSKImpact"),
        "msk_heme": record.get("mSKHeme"),
        "grch37_refseq": record.get("grch37RefSeq"),
        "grch37_isoform": record.get("grch37Isoform"),
        "grch38_refseq": record.get("grch38RefSeq"),
        "grch38_isoform": record.get("grch38Isoform"),
    }


def _public_gene_summary_from_curated_gene(
    *,
    record: dict[str, Any],
    hgnc_collection: Any | None,
    hgnc_symbol_index: dict[str, dict[str, Any]] | None = None,
    source: str,
) -> dict[str, Any] | None:
    """Build a normalized public gene-summary marker from one curated gene record."""
    symbol = _extract_oncokb_gene_symbol(record)
    if not symbol:
        return None
    hgnc_doc = _hgnc_doc_for_record(
        record,
        hgnc_collection,
        symbol_index=hgnc_symbol_index,
    )
    approved_symbol = str((hgnc_doc or {}).get("hgnc_symbol") or symbol).strip()
    return {
        "gene": approved_symbol,
        "source": source,
        "public_api": True,
        "therapeutic_data_included": False,
        "data_version": record.get("dataVersion") or record.get("version"),
        "gene_exist": True,
        "gene_summary": record.get("summary"),
        "background": record.get("background"),
        "setting": record.get("setting"),
        "hgnc_id": (hgnc_doc or {}).get("hgnc_id") or (hgnc_doc or {}).get("_id"),
        "previous_symbols": (hgnc_doc or {}).get("prev_symbol") or [],
        "alias_symbols": (hgnc_doc or {}).get("alias_symbol") or [],
        "entrez_gene_id": record.get("entrezGeneId"),
        "gene_type": record.get("geneType"),
        "highest_sensitive_level": record.get("highestSensitiveLevel"),
        "highest_resistance_level": record.get("highestResistanceLevel")
        or record.get("highestResistancLevel"),
        "grch37_refseq": record.get("grch37RefSeq"),
        "grch37_isoform": record.get("grch37Isoform"),
        "grch38_refseq": record.get("grch38RefSeq"),
        "grch38_isoform": record.get("grch38Isoform"),
    }
