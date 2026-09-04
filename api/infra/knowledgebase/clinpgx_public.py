"""ClinPGx public API client and local knowledgebase repositories."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from pymongo import UpdateOne

from api.infra.mongo.repositories.base import BaseRepository


def _utc_now() -> datetime:
    """Return an aware UTC timestamp for cache records."""
    return datetime.now(timezone.utc)


def _clean(value: Any) -> str:
    """Normalize one scalar TSV/API value."""
    return str(value or "").strip()


def _split_list(value: Any) -> list[str]:
    """Split semicolon/comma-delimited ClinPGx TSV fields."""
    text = _clean(value)
    if not text:
        return []
    parts: list[str] = []
    for chunk in text.replace(";", ",").split(","):
        item = chunk.strip()
        if item and item not in parts:
            parts.append(item)
    return parts


def _bool(value: Any) -> bool:
    """Parse ClinPGx yes/no boolean fields."""
    return _clean(value).lower() in {"true", "yes", "y", "1"}


def _int_or_none(value: Any) -> int | None:
    """Parse optional integer fields from TSV/API values."""
    text = _clean(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _source_version_from_zip(zip_path: Path) -> dict[str, str | None]:
    """Read bundled ClinPGx metadata from the provided zip."""
    metadata = {"reference": None, "created": None}
    with zipfile.ZipFile(zip_path) as archive:
        try:
            metadata["reference"] = archive.read("VERSIONS.txt").decode("utf-8").strip()
        except KeyError:
            metadata["reference"] = None
        created_name = next(
            (name for name in archive.namelist() if name.startswith("CREATED_")), None
        )
        if created_name:
            metadata["created"] = archive.read(created_name).decode("utf-8").strip()
    return metadata


def normalize_clinpgx_gene_row(
    row: dict[str, Any],
    *,
    source_file: str,
    source_reference: str | None,
    source_created: str | None,
) -> dict[str, Any]:
    """Convert one ClinPGx genes.tsv row into the Coyote3 public cache shape."""
    symbol = _clean(row.get("Symbol"))
    return {
        "pharmgkb_accession_id": _clean(row.get("PharmGKB Accession Id")),
        "ncbi_gene_id": _int_or_none(row.get("NCBI Gene ID")),
        "hgnc_id": _clean(row.get("HGNC ID")) or None,
        "ensembl_id": _clean(row.get("Ensembl Id")) or None,
        "name": _clean(row.get("Name")) or None,
        "symbol": symbol,
        "alternate_names": _split_list(row.get("Alternate Names")),
        "alternate_symbols": _split_list(row.get("Alternate Symbols")),
        "is_vip": _bool(row.get("Is VIP")),
        "has_variant_annotation": _bool(row.get("Has Variant Annotation")),
        "has_cpic_dosing_guideline": _bool(row.get("Has CPIC Dosing Guideline")),
        "cross_references": _split_list(row.get("Cross-references")),
        "chromosome": _clean(row.get("Chromosome")) or None,
        "grch37_start": _int_or_none(row.get("Chromosomal Start - GRCh37")),
        "grch37_stop": _int_or_none(row.get("Chromosomal Stop - GRCh37")),
        "grch38_start": _int_or_none(row.get("Chromosomal Start - GRCh38")),
        "grch38_stop": _int_or_none(row.get("Chromosomal Stop - GRCh38")),
        "source": "api.clinpgx.org",
        "source_file": source_file,
        "source_reference": source_reference,
        "source_created": source_created,
        "public_api": True,
        "last_seen_at": _utc_now(),
    }


class ClinPgxPublicClient:
    """Small synchronous client for explicit ClinPGx public API lookups."""

    def __init__(self, *, base_url: str, timeout: float = 3.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """Fetch one ClinPGx API endpoint and return the JSON payload."""
        response = httpx.get(f"{self.base_url}{path}", params=params or {}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_gene(
        self, *, clinpgx_id: str | None = None, symbol: str | None = None
    ) -> dict[str, Any]:
        """Fetch one ClinPGx gene by identifier, falling back to symbol query."""
        if clinpgx_id:
            return self._unwrap_data(self._get(f"/data/gene/{clinpgx_id}", params={"view": "max"}))
        if symbol:
            return self._unwrap_data(
                self._get("/data/gene", params={"symbol": symbol, "view": "max"})
            )
        return {}

    def get_gene_knowledge(
        self,
        *,
        clinpgx_id: str | None = None,
        symbol: str | None = None,
        max_items: int = 12,
    ) -> dict[str, Any]:
        """Fetch and normalize ClinPGx gene-level public knowledge."""
        gene = self.get_gene(clinpgx_id=clinpgx_id, symbol=symbol)
        accession_id = _clean(gene.get("id") if isinstance(gene, dict) else None) or _clean(
            clinpgx_id
        )
        approved_symbol = _clean(gene.get("symbol") if isinstance(gene, dict) else None) or _clean(
            symbol
        )
        if not accession_id and not approved_symbol:
            return {}

        guideline_annotations = self._safe_list(
            "/data/guidelineAnnotation",
            {"relatedGenes.accessionId": accession_id, "view": "min"},
            enabled=bool(accession_id),
        )
        label_annotations = self._safe_list(
            "/data/label",
            {"relatedGenes.accessionId": accession_id, "view": "min"},
            enabled=bool(accession_id),
        )
        variant_annotations = self._safe_list(
            "/data/variantAnnotation",
            {"location.genes.symbol": approved_symbol, "view": "min"},
            enabled=bool(approved_symbol),
        )
        connected_chemicals = self._safe_list(
            f"/report/connectedObjects/{accession_id}/Chemical",
            {},
            enabled=bool(accession_id),
        )
        connected_pathways = self._safe_list(
            f"/report/connectedObjects/{accession_id}/Pathway",
            {},
            enabled=bool(accession_id),
        )
        return build_clinpgx_knowledge_summary(
            gene=gene,
            guidelines=guideline_annotations,
            labels=label_annotations,
            variant_annotations=variant_annotations,
            chemicals=connected_chemicals,
            pathways=connected_pathways,
            query={"clinpgx_id": accession_id, "symbol": approved_symbol},
            max_items=max_items,
        )

    def _safe_list(
        self, path: str, params: dict[str, Any], *, enabled: bool
    ) -> list[dict[str, Any]]:
        """Return an API result list, letting network/HTTP errors bubble up."""
        if not enabled:
            return []
        return self._as_list(self._get(path, params=params))

    @staticmethod
    def _unwrap_data(payload: Any) -> dict[str, Any]:
        """Return the first useful object from a ClinPGx response payload."""
        if isinstance(payload, dict) and "data" in payload:
            data = payload.get("data")
            if isinstance(data, list):
                return data[0] if data else {}
            return data if isinstance(data, dict) else {}
        if isinstance(payload, list):
            return payload[0] if payload else {}
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _as_list(cls, payload: Any) -> list[dict[str, Any]]:
        """Return a list from ClinPGx payloads that may wrap data in a `data` key."""
        if isinstance(payload, dict) and "data" in payload:
            payload = payload.get("data")
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
        return []


def _html_to_text(value: Any) -> str:
    """Lightweight HTML-to-text conversion for public API summaries."""
    import re

    text = _clean(value)
    if not text:
        return ""
    text = re.sub(r"<br\\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|li|ul|ol)>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())


def _object_name(row: dict[str, Any]) -> str:
    """Return a display name from a ClinPGx object or connected-object row."""
    connected = row.get("connectedObject") if isinstance(row.get("connectedObject"), dict) else row
    return _clean(connected.get("name") or connected.get("symbol") or connected.get("id"))


def _object_id(row: dict[str, Any]) -> str:
    """Return an accession identifier from a ClinPGx object or connected-object row."""
    connected = row.get("connectedObject") if isinstance(row.get("connectedObject"), dict) else row
    return _clean(connected.get("id") or connected.get("accessionId"))


def _short_object(row: dict[str, Any]) -> dict[str, Any]:
    """Build a compact object summary for the knowledge cache."""
    return {
        "id": _object_id(row),
        "name": _object_name(row),
        "type": _clean((row.get("connectedObject") or row).get("objCls")),
        "connection_types": list(row.get("connectionTypes") or []),
    }


def _short_annotation(row: dict[str, Any]) -> dict[str, Any]:
    """Build a compact annotation summary from ClinPGx API records."""
    return {
        "id": _clean(row.get("accessionId") or row.get("id")),
        "name": _clean(row.get("name")),
        "type": _clean(row.get("objCls")),
        "sentence": _clean(row.get("sentence")),
        "description": _clean(row.get("description")),
        "significance": _clean((row.get("significance") or {}).get("term"))
        if isinstance(row.get("significance"), dict)
        else _clean(row.get("significance")),
        "score": row.get("score"),
        "phenotype_categories": [
            _clean(item.get("term"))
            for item in row.get("phenotypeCategories", [])
            if isinstance(item, dict)
        ],
        "literature": {
            "pmid": next(
                (
                    _clean(ref.get("resourceId"))
                    for ref in (row.get("literature") or {}).get("crossReferences", [])
                    if isinstance(ref, dict) and _clean(ref.get("resource")).lower() == "pubmed"
                ),
                None,
            )
            if isinstance(row.get("literature"), dict)
            else None,
            "title": _clean((row.get("literature") or {}).get("title"))
            if isinstance(row.get("literature"), dict)
            else None,
        },
    }


def _top_chemicals(rows: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
    """Return the most clinically annotated connected chemicals first."""
    priority = {
        "Guideline Annotation": 7,
        "Label Annotation": 6,
        "Clinical Annotation": 5,
        "Variant Annotation": 4,
        "Multilink Annotation": 3,
        "Literature": 2,
        "Pathway": 1,
    }

    def score(row: dict[str, Any]) -> tuple[int, str]:
        types = list(row.get("connectionTypes") or [])
        return (max([priority.get(item, 0) for item in types] or [0]), _object_name(row).lower())

    return [_short_object(row) for row in sorted(rows, key=score, reverse=True)[:max_items]]


def build_clinpgx_knowledge_summary(
    *,
    gene: dict[str, Any],
    guidelines: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    variant_annotations: list[dict[str, Any]],
    chemicals: list[dict[str, Any]],
    pathways: list[dict[str, Any]],
    query: dict[str, Any],
    max_items: int = 12,
) -> dict[str, Any]:
    """Normalize a ClinPGx API gene knowledge response for storage and UI use."""
    vip_summary = gene.get("vipSummary") if isinstance(gene.get("vipSummary"), dict) else {}
    terms = gene.get("terms") if isinstance(gene.get("terms"), list) else []
    cross_references = (
        gene.get("crossReferences") if isinstance(gene.get("crossReferences"), list) else []
    )
    summary = {
        "clinpgx_id": _clean(gene.get("id") or query.get("clinpgx_id")),
        "symbol": _clean(gene.get("symbol") or query.get("symbol")),
        "name": _clean(gene.get("name")),
        "source": "api.clinpgx.org",
        "public_api": True,
        "license": "CC BY-SA 4.0; subject to ClinPGx Data Usage Policy",
        "query": query,
        "gene": {
            "id": _clean(gene.get("id")),
            "symbol": _clean(gene.get("symbol")),
            "name": _clean(gene.get("name")),
            "allele_file": _clean(gene.get("alleleFile")),
            "allele_function_source": _clean(gene.get("alleleFunctionSource")),
            "allele_type": _clean(gene.get("alleleType")),
            "build_version": _clean(gene.get("buildVersion")),
            "chromosome": _clean((gene.get("chr") or {}).get("name"))
            if isinstance(gene.get("chr"), dict)
            else None,
            "strand": _clean(gene.get("strand")),
            "chr_start_b37": gene.get("chrStartPosB37") or gene.get("chrStart"),
            "chr_stop_b37": gene.get("chrStopPosB37") or gene.get("chrStop"),
            "chr_start_b38": gene.get("chrStartPosB38"),
            "chr_stop_b38": gene.get("chrStopPosB38"),
            "alt_symbols": list((gene.get("altNames") or {}).get("symbol") or [])
            if isinstance(gene.get("altNames"), dict)
            else [],
            "alt_synonyms": list((gene.get("altNames") or {}).get("synonym") or [])
            if isinstance(gene.get("altNames"), dict)
            else [],
        },
        "flags": {
            "vip": bool(gene.get("vipId") or gene.get("vipSummary")),
            "vip_tier": _clean(gene.get("vipTier")),
            "cpic_gene": bool(gene.get("cpicGene")),
            "amp": bool(gene.get("amp")),
            "pharmvar_gene": bool(gene.get("pharmVarGene")),
            "has_non_standard_haplotypes": bool(gene.get("hasNonStandardHaplotypes")),
        },
        "vip": {
            "id": _clean(gene.get("vipId")),
            "tier": _clean(gene.get("vipTier")),
            "summary": _html_to_text(vip_summary.get("html")),
            "citation": {
                "title": _clean((gene.get("vipCitation") or {}).get("title"))
                if isinstance(gene.get("vipCitation"), dict)
                else None,
                "pmid": next(
                    (
                        _clean(ref.get("resourceId"))
                        for ref in (gene.get("vipCitation") or {}).get("crossReferences", [])
                        if isinstance(ref, dict) and _clean(ref.get("resource")).lower() == "pubmed"
                    ),
                    None,
                )
                if isinstance(gene.get("vipCitation"), dict)
                else None,
            },
        },
        "counts": {
            "guideline_annotations": len(guidelines),
            "label_annotations": len(labels),
            "variant_annotations": len(variant_annotations),
            "connected_chemicals": len(chemicals),
            "pathways": len(pathways),
            "cross_references": len(cross_references),
            "ontology_terms": len(terms),
        },
        "guidelines": [_short_annotation(row) for row in guidelines[:max_items]],
        "labels": [_short_annotation(row) for row in labels[:max_items]],
        "variant_annotations": [_short_annotation(row) for row in variant_annotations[:max_items]],
        "top_chemicals": _top_chemicals(chemicals, max_items=max_items),
        "pathways": [_short_object(row) for row in pathways[:max_items]],
        "cross_references": [
            {
                "resource": _clean(row.get("resource")),
                "resource_id": _clean(row.get("resourceId")),
                "url": _clean(row.get("_url")),
            }
            for row in cross_references[:max_items]
            if isinstance(row, dict)
        ],
        "ontology_terms": [
            {
                "resource": _clean(row.get("resource")),
                "term": _clean(row.get("term")),
                "term_id": _clean(row.get("termId")),
            }
            for row in terms[:max_items]
            if isinstance(row, dict)
        ],
        "retrieved_at": _utc_now(),
    }
    return summary


class ClinPgxPublicRepository(BaseRepository):
    """Local cache for ClinPGx public gene records."""

    def __init__(self, adapter):
        """Bind the ClinPGx public gene cache collection."""
        super().__init__(adapter)
        self.set_collection(self.adapter.clinpgx_genes_public_collection)

    def ensure_indexes(self) -> None:
        """Create indexes used by table badge lookups and operational imports."""
        collection = self.get_collection()
        collection.create_index([("symbol", 1)], name="symbol_1", unique=True, background=True)
        collection.create_index([("hgnc_id", 1)], name="hgnc_id_1", background=True)
        collection.create_index(
            [("pharmgkb_accession_id", 1)],
            name="pharmgkb_accession_id_1",
            background=True,
        )

    def get_summary(self) -> dict[str, Any]:
        """Return aggregate public ClinPGx gene capability statistics."""
        collection = self.get_collection()
        total = int(collection.estimated_document_count() or 0)
        if not total:
            return {"available": False, "total": 0, "distribution": [], "metrics": []}
        fields = (
            ("VIP genes", "is_vip"),
            ("CPIC dosing guidance", "has_cpic_dosing_guideline"),
            ("Variant annotations", "has_variant_annotation"),
        )
        return {
            "available": True,
            "total": total,
            "distribution": [],
            "metrics": [
                {"name": label, "value": int(collection.count_documents({field: True}))}
                for label, field in fields
            ],
        }
        collection.create_index(
            [("alternate_symbols", 1)], name="alternate_symbols_1", background=True
        )
        collection.create_index(
            [("is_vip", 1), ("has_cpic_dosing_guideline", 1), ("has_variant_annotation", 1)],
            name="pgx_flags_1",
            background=True,
        )

    def import_gene_zip(self, zip_path: str | Path) -> dict[str, int]:
        """Upsert records from a ClinPGx genes.tsv zip export."""
        path = Path(zip_path)
        metadata = _source_version_from_zip(path)
        now = _utc_now()
        operations: list[UpdateOne] = []
        with zipfile.ZipFile(path) as archive:
            with archive.open("genes.tsv") as handle:
                wrapper = io.TextIOWrapper(handle, encoding="utf-8")
                reader = csv.DictReader(wrapper, delimiter="\t")
                for row in reader:
                    doc = normalize_clinpgx_gene_row(
                        row,
                        source_file=str(path),
                        source_reference=metadata["reference"],
                        source_created=metadata["created"],
                    )
                    symbol = doc.get("symbol")
                    if not symbol:
                        continue
                    doc["last_seen_at"] = now
                    operations.append(
                        UpdateOne(
                            {"symbol": symbol},
                            {
                                "$set": doc,
                                "$setOnInsert": {"created_on": now},
                            },
                            upsert=True,
                        )
                    )
        if not operations:
            return {"matched": 0, "modified": 0, "upserted": 0, "total": 0}
        result = self.get_collection().bulk_write(operations, ordered=False)
        return {
            "matched": int(result.matched_count),
            "modified": int(result.modified_count),
            "upserted": int(result.upserted_count),
            "total": len(operations),
        }

    def get_gene_record(self, gene: str | None) -> dict[str, Any] | None:
        """Return one ClinPGx gene cache row by approved symbol or alias."""
        symbol = _clean(gene)
        if not symbol:
            return None
        return self.get_collection().find_one(
            {
                "$or": [
                    {"symbol": symbol},
                    {"alternate_symbols": symbol},
                ]
            }
        )

    def get_gene_records(self, genes: list[str]) -> dict[str, dict[str, Any]]:
        """Return ClinPGx gene records keyed by the requested or approved symbol."""
        normalized = sorted({_clean(gene) for gene in genes if _clean(gene)})
        if not normalized:
            return {}
        rows = self.get_collection().find(
            {
                "$or": [
                    {"symbol": {"$in": normalized}},
                    {"alternate_symbols": {"$in": normalized}},
                ]
            }
        )
        records: dict[str, dict[str, Any]] = {}
        for row in rows:
            approved = _clean(row.get("symbol"))
            aliases = set(_split_list(row.get("alternate_symbols")))
            if approved:
                records[approved] = row
            for requested in normalized:
                if requested == approved or requested in aliases:
                    records[requested] = row
        return records
