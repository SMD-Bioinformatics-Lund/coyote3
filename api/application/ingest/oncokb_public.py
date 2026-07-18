"""Ingest-time public OncoKB enrichment helpers."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from api.infra.knowledgebase.public_oncokb import PublicOncoKbClient

logger = logging.getLogger(__name__)


def _chunks(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    """Yield fixed-size chunks from a list."""
    safe_size = max(1, int(size or 1))
    for idx in range(0, len(items), safe_size):
        yield items[idx : idx + safe_size]


def _variant_id(value: Any) -> str:
    """Serialize a variant identifier for cache metadata."""
    return str(value or "")


def _gene_record_from_annotation(
    *,
    gene: str,
    response: dict[str, Any] | None,
    source: str,
) -> dict[str, Any]:
    """Build a public OncoKB gene marker record from an annotation response."""
    payload = response if isinstance(response, dict) else {}
    return {
        "gene": gene,
        "source": source,
        "public_api": True,
        "therapeutic_data_included": False,
        "data_version": payload.get("dataVersion"),
        "gene_exist": payload.get("geneExist"),
        "gene_summary": payload.get("geneSummary") or payload.get("oncokbGeneSummary"),
    }


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


def _hgnc_doc_for_symbol(symbol: str, hgnc_collection: Any | None) -> dict[str, Any] | None:
    """Return HGNC metadata by approved, previous, or alias symbol."""
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


def _public_gene_marker_from_cancer_gene(
    *,
    record: dict[str, Any],
    hgnc_collection: Any | None,
    source: str,
) -> dict[str, Any] | None:
    """Build a normalized public cancer-gene marker from one OncoKB record."""
    symbol = _extract_oncokb_gene_symbol(record)
    if not symbol:
        return None
    hgnc_doc = _hgnc_doc_for_symbol(symbol, hgnc_collection)
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
    source: str,
) -> dict[str, Any] | None:
    """Build a normalized public gene-summary marker from one curated gene record."""
    symbol = _extract_oncokb_gene_symbol(record)
    if not symbol:
        return None
    hgnc_doc = _hgnc_doc_for_symbol(symbol, hgnc_collection)
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


def ensure_public_oncokb_gene_cache(
    *,
    client: PublicOncoKbClient,
    cache_repository: Any,
    hgnc_collection: Any | None = None,
) -> dict[str, int]:
    """Seed the public OncoKB cancer-gene marker cache once from the public API."""
    if cache_repository.public_cancer_gene_count() > 0:
        return {"fetched": 0, "genes_upserted": 0}
    source = "public.api.oncokb.org"
    records = client.cancer_gene_list()
    docs = [
        doc
        for record in records
        if (
            doc := _public_gene_marker_from_cancer_gene(
                record=record,
                hgnc_collection=hgnc_collection,
                source=source,
            )
        )
    ]
    return {
        "fetched": len(records),
        "genes_upserted": cache_repository.upsert_cancer_gene_markers(docs),
    }


def seed_public_oncokb_curated_gene_cache(
    *,
    client: PublicOncoKbClient,
    cache_repository: Any,
    hgnc_collection: Any | None = None,
    include_evidence: bool = True,
    refresh: bool = False,
) -> dict[str, int]:
    """Seed public OncoKB curated-gene summaries from /utils/allCuratedGenes."""
    if not refresh and cache_repository.public_gene_count() > 0:
        return {"fetched": 0, "genes_upserted": 0}
    source = "public.api.oncokb.org"
    records = client.all_curated_genes(include_evidence=include_evidence)
    docs = [
        doc
        for record in records
        if (
            doc := _public_gene_summary_from_curated_gene(
                record=record,
                hgnc_collection=hgnc_collection,
                source=source,
            )
        )
    ]
    return {
        "fetched": len(records),
        "genes_upserted": cache_repository.upsert_gene_markers(docs),
    }


def enrich_public_oncokb_cache(
    *,
    sample: dict[str, Any],
    variants: list[dict[str, Any]],
    client: PublicOncoKbClient,
    cache_repository: Any,
    batch_size: int,
    hgnc_collection: Any | None = None,
) -> dict[str, int]:
    """Batch query and persist missing public OncoKB annotation records.

    Public OncoKB is used only as a cache-building source here. Cache identity
    is based on HGVSg when available, otherwise gene, protein alteration,
    reference genome, and evidence type. Repeated variants across samples reuse
    the same annotation record.
    """
    candidates: dict[str, dict[str, Any]] = {}
    skipped = 0
    sample_id = str(sample.get("_id") or "")
    sample_name = str(sample.get("name") or "")
    now = datetime.now(timezone.utc)
    oncokb_genes = cache_repository.public_cancer_gene_symbols()

    for variant in variants:
        built_query = client.build_annotation_query(sample=sample, variant=variant)
        if built_query is None:
            skipped += 1
            continue
        query_method, query = built_query
        query_hash = client.query_hash(query)
        gene = str(
            (query.get("gene") or {}).get("hugoSymbol")
            or (variant.get("INFO", {}).get("selected_CSQ", {}) or {}).get("SYMBOL")
            or ""
        )
        if gene not in oncokb_genes:
            skipped += 1
            continue
        existing = candidates.get(query_hash)
        if existing is None:
            candidates[query_hash] = {
                "query_hash": query_hash,
                "query_method": query_method,
                "query": query,
                "gene": gene,
                "hgvsg": query.get("hgvsg"),
                "alteration": query.get("alteration"),
                "reference_genome": query.get("referenceGenome"),
                "variant_ids": [_variant_id(variant.get("_id"))],
                "sample_ids": [sample_id] if sample_id else [],
                "sample_names": [sample_name] if sample_name else [],
            }
            continue
        variant_id = _variant_id(variant.get("_id"))
        if variant_id and variant_id not in existing["variant_ids"]:
            existing["variant_ids"].append(variant_id)
        if sample_id and sample_id not in existing["sample_ids"]:
            existing["sample_ids"].append(sample_id)
        if sample_name and sample_name not in existing["sample_names"]:
            existing["sample_names"].append(sample_name)

    if not candidates:
        return {
            "queried": 0,
            "inserted": 0,
            "genes_upserted": 0,
            "skipped": skipped,
            "cached": 0,
            "genes_seeded": 0,
        }

    existing_hashes = cache_repository.existing_query_hashes(list(candidates))
    missing = [record for key, record in candidates.items() if key not in existing_hashes]
    cached = len(candidates) - len(missing)
    if not missing:
        return {
            "queried": 0,
            "inserted": 0,
            "genes_upserted": 0,
            "skipped": skipped,
            "cached": cached,
            "genes_seeded": 0,
        }

    annotation_docs: list[dict[str, Any]] = []
    gene_docs_by_gene: dict[str, dict[str, Any]] = {}
    source = "public.api.oncokb.org"
    missing_by_method: dict[str, list[dict[str, Any]]] = {
        "hgvsg": [record for record in missing if record.get("query_method") == "hgvsg"],
        "protein_change": [
            record for record in missing if record.get("query_method") == "protein_change"
        ],
    }
    for query_method, method_records in missing_by_method.items():
        if not method_records:
            continue
        annotation_method = (
            client.annotate_hgvsgs if query_method == "hgvsg" else client.annotate_protein_changes
        )
        for batch in _chunks(method_records, batch_size):
            try:
                responses = annotation_method([item["query"] for item in batch])
            except Exception as exc:
                logger.warning(
                    "public_oncokb_batch_enrichment_failed sample=%s method=%s batch_size=%s error=%s",
                    sample_name or sample_id,
                    query_method,
                    len(batch),
                    exc,
                )
                skipped += len(batch)
                continue
            for record, response in zip(batch, responses, strict=False):
                gene = str(record.get("gene") or "")
                annotation_docs.append(
                    {
                        "query_hash": record["query_hash"],
                        "query_method": record.get("query_method"),
                        "source": source,
                        "license": "public; therapeutic data excluded",
                        "public_api": True,
                        "therapeutic_data_included": False,
                        "gene": gene,
                        "hgvsg": record.get("hgvsg"),
                        "alteration": record.get("alteration"),
                        "reference_genome": record.get("reference_genome"),
                        "query": record.get("query"),
                        "response": response,
                        "data_version": response.get("dataVersion")
                        if isinstance(response, dict)
                        else None,
                        "gene_exist": response.get("geneExist")
                        if isinstance(response, dict)
                        else None,
                        "variant_exist": response.get("variantExist")
                        if isinstance(response, dict)
                        else None,
                        "variant_ids": record.get("variant_ids") or [],
                        "sample_ids": record.get("sample_ids") or [],
                        "sample_names": record.get("sample_names") or [],
                        "queried_at": now,
                        "created_on": now,
                    }
                )
                if gene:
                    gene_docs_by_gene[gene] = _gene_record_from_annotation(
                        gene=gene,
                        response=response if isinstance(response, dict) else None,
                        source=source,
                    )

    inserted = cache_repository.insert_missing_annotations(annotation_docs)
    genes_upserted = cache_repository.upsert_gene_markers(list(gene_docs_by_gene.values()))
    return {
        "queried": len(annotation_docs),
        "inserted": inserted,
        "genes_upserted": genes_upserted,
        "skipped": skipped,
        "cached": cached,
        "genes_seeded": 0,
    }
