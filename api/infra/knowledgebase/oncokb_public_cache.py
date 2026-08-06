"""Mongo repository for public OncoKB annotation cache records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import BulkWriteError, DuplicateKeyError

from api.contracts.operations import OperationResult
from api.infra.mongo.repositories.base import BaseRepository


def _utc_now() -> datetime:
    """Return an aware UTC timestamp for cache records."""
    return datetime.now(timezone.utc)


def _as_symbol_list(value: Any) -> list[str]:
    """Normalize one symbol or a list of symbols into clean strings."""
    if value is None:
        return []
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if isinstance(value, list | tuple | set):
        return [str(item).strip() for item in value if str(item or "").strip()]
    return [str(value).strip()] if str(value or "").strip() else []


def _merge_public_gene_records(
    *,
    cancer_gene: dict[str, Any] | None,
    gene_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return one UI-facing public OncoKB gene record from both public caches."""
    if not cancer_gene and not gene_summary:
        return None
    merged: dict[str, Any] = {}
    if gene_summary:
        merged.update(gene_summary)
        merged["public_gene_summary"] = gene_summary
    if cancer_gene:
        merged.update(cancer_gene)
        merged["public_cancer_gene"] = cancer_gene
    if gene_summary:
        for key in (
            "gene_summary",
            "background",
            "setting",
            "highest_sensitive_level",
            "highest_resistance_level",
        ):
            if gene_summary.get(key) is not None:
                merged[key] = gene_summary.get(key)
    merged["public_api"] = True
    merged["therapeutic_data_included"] = False
    return merged


def _present_cache_fields(payload: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """Return only fields supplied by an API response so partial refreshes do not erase data."""
    return {field: payload[field] for field in fields if field in payload}


class OncoKbPublicCacheRepository(BaseRepository):
    """Persist public OncoKB variant and gene cache records."""

    def __init__(self, adapter):
        """Bind the variant-level public cache collection."""
        super().__init__(adapter)
        self.set_collection(self.adapter.oncokb_public_collection)

    @property
    def gene_collection(self):
        """Return the public OncoKB gene marker cache collection."""
        return self.adapter.oncokb_genes_public_collection

    @property
    def cancer_gene_collection(self):
        """Return public OncoKB cancer-gene list cache collection."""
        return self.adapter.oncokb_cancer_genes_public_collection

    def ensure_indexes(self) -> None:
        """Create indexes for cache identity and UI lookup paths."""
        self.get_collection().create_index(
            [("query_hash", 1)],
            name="query_hash_1",
            unique=True,
            background=True,
        )
        self.get_collection().create_index(
            [("gene", 1), ("alteration", 1), ("reference_genome", 1)],
            name="gene_alteration_reference_1",
            background=True,
        )
        self.get_collection().create_index([("gene", 1)], name="gene_1", background=True)
        self.get_collection().create_index(
            [("queried_at", -1)], name="queried_at_-1", background=True
        )
        self.gene_collection.create_index(
            [("gene", 1)],
            name="gene_1",
            unique=True,
            background=True,
        )
        self.gene_collection.create_index(
            [("last_seen_at", -1)],
            name="last_seen_at_-1",
            background=True,
        )
        self.cancer_gene_collection.create_index(
            [("gene", 1)],
            name="gene_1",
            unique=True,
            background=True,
        )
        self.cancer_gene_collection.create_index(
            [("last_seen_at", -1)],
            name="last_seen_at_-1",
            background=True,
        )
        self.cancer_gene_collection.create_index(
            [("oncokb_annotated", 1), ("gene_type", 1)],
            name="oncokb_annotated_gene_type_1",
            background=True,
        )

    def existing_query_hashes(self, query_hashes: list[str]) -> set[str]:
        """Return public OncoKB query hashes already present in the cache."""
        hashes = sorted({str(value) for value in query_hashes if value})
        if not hashes:
            return set()
        rows = self.get_collection().find({"query_hash": {"$in": hashes}}, {"query_hash": 1})
        return {str(row.get("query_hash")) for row in rows if row.get("query_hash")}

    def remove_sample_references(
        self, *, sample_id: str, sample_name: str | None = None
    ) -> OperationResult:
        """Remove one deleted sample from shared public annotation cache records."""
        pull: dict[str, str] = {"sample_ids": str(sample_id)}
        if sample_name:
            pull["sample_names"] = str(sample_name)
        result = self.get_collection().update_many(
            {
                "$or": [
                    {"sample_ids": str(sample_id)},
                    *([{"sample_names": str(sample_name)}] if sample_name else []),
                ]
            },
            {"$pull": pull},
        )
        return OperationResult.from_update(result)

    def public_gene_count(self) -> int:
        """Return the number of public OncoKB gene marker records."""
        return int(self.gene_collection.estimated_document_count() or 0)

    def public_cancer_gene_count(self) -> int:
        """Return the number of public OncoKB cancer-gene marker records."""
        return int(self.cancer_gene_collection.estimated_document_count() or 0)

    def public_gene_symbols(self) -> set[str]:
        """Return all public OncoKB gene symbols currently cached."""
        return {
            str(gene) for gene in self.gene_collection.distinct("gene") if str(gene or "").strip()
        }

    def public_cancer_gene_symbols(self) -> set[str]:
        """Return public OncoKB cancer-gene symbols and known symbol aliases."""
        symbols: set[str] = set()
        rows = self.cancer_gene_collection.find(
            {},
            {"gene": 1, "previous_symbols": 1, "alias_symbols": 1},
        )
        for row in rows:
            for value in (
                [row.get("gene")]
                + _as_symbol_list(row.get("previous_symbols"))
                + _as_symbol_list(row.get("alias_symbols"))
            ):
                symbol = str(value or "").strip()
                if symbol:
                    symbols.add(symbol)
        return symbols

    def insert_missing_annotations(self, docs: list[dict[str, Any]]) -> int:
        """Insert new annotation records and ignore duplicate query hashes."""
        if not docs:
            return 0
        now = _utc_now()
        prepared: list[dict[str, Any]] = []
        for doc in docs:
            record = dict(doc)
            record.setdefault("created_on", now)
            record.setdefault("queried_at", now)
            prepared.append(record)
        try:
            result = self.get_collection().insert_many(prepared, ordered=False)
            return len(result.inserted_ids)
        except BulkWriteError as exc:
            write_errors = exc.details.get("writeErrors", []) if exc.details else []
            duplicate_errors = [err for err in write_errors if err.get("code") == 11000]
            if len(duplicate_errors) != len(write_errors):
                raise
            return max(0, len(prepared) - len(duplicate_errors))

    def upsert_gene_markers(self, docs: list[dict[str, Any]]) -> int:
        """Create or refresh public OncoKB gene marker records."""
        changed = 0
        now = _utc_now()
        for doc in docs:
            gene = str(doc.get("gene") or "").strip()
            if not gene:
                continue
            payload = dict(doc)
            payload.setdefault("created_on", now)
            payload["last_seen_at"] = now
            update_fields = _present_cache_fields(
                payload,
                (
                    "source",
                    "public_api",
                    "therapeutic_data_included",
                    "data_version",
                    "gene_exist",
                    "gene_summary",
                    "background",
                    "setting",
                    "entrez_gene_id",
                    "gene_type",
                    "highest_sensitive_level",
                    "highest_resistance_level",
                    "grch37_refseq",
                    "grch37_isoform",
                    "grch38_refseq",
                    "grch38_isoform",
                    "hgnc_id",
                    "previous_symbols",
                    "alias_symbols",
                ),
            )
            update_fields["last_seen_at"] = now
            existing = self.gene_collection.find_one(
                {"gene": gene},
                {field: 1 for field in update_fields if field != "last_seen_at"},
            )
            content_changed = existing is None or any(
                existing.get(field) != value
                for field, value in update_fields.items()
                if field != "last_seen_at"
            )
            try:
                result = self.gene_collection.update_one(
                    {"gene": gene},
                    {
                        "$set": update_fields,
                        "$setOnInsert": {
                            "gene": gene,
                            "created_on": payload["created_on"],
                        },
                    },
                    upsert=True,
                )
            except DuplicateKeyError:
                continue
            changed += int(result.upserted_id is not None or content_changed)
        return changed

    def upsert_cancer_gene_markers(self, docs: list[dict[str, Any]]) -> int:
        """Create or refresh public OncoKB cancer-gene list marker records."""
        changed = 0
        now = _utc_now()
        for doc in docs:
            gene = str(doc.get("gene") or "").strip()
            if not gene:
                continue
            payload = dict(doc)
            payload.setdefault("created_on", now)
            payload["last_seen_at"] = now
            update_fields = _present_cache_fields(
                payload,
                (
                    "source",
                    "public_api",
                    "therapeutic_data_included",
                    "data_version",
                    "hgnc_id",
                    "previous_symbols",
                    "alias_symbols",
                    "entrez_gene_id",
                    "gene_type",
                    "occurrence_count",
                    "oncokb_annotated",
                    "sanger_cgc",
                    "vogelstein",
                    "foundation",
                    "foundation_heme",
                    "msk_impact",
                    "msk_heme",
                    "grch37_refseq",
                    "grch37_isoform",
                    "grch38_refseq",
                    "grch38_isoform",
                ),
            )
            update_fields["last_seen_at"] = now
            existing = self.cancer_gene_collection.find_one(
                {"gene": gene},
                {field: 1 for field in update_fields if field != "last_seen_at"},
            )
            content_changed = existing is None or any(
                existing.get(field) != value
                for field, value in update_fields.items()
                if field != "last_seen_at"
            )
            try:
                result = self.cancer_gene_collection.update_one(
                    {"gene": gene},
                    {
                        "$set": update_fields,
                        "$setOnInsert": {
                            "gene": gene,
                            "created_on": payload["created_on"],
                        },
                    },
                    upsert=True,
                )
            except DuplicateKeyError:
                continue
            changed += int(result.upserted_id is not None or content_changed)
        return changed

    def get_gene_record(self, gene: str | None) -> dict[str, Any] | None:
        """Return one UI-facing public OncoKB gene record by symbol."""
        symbol = str(gene or "").strip()
        if not symbol:
            return None
        symbol_query = {
            "$or": [
                {"gene": symbol},
                {"previous_symbols": symbol},
                {"alias_symbols": symbol},
            ]
        }
        return _merge_public_gene_records(
            cancer_gene=self.cancer_gene_collection.find_one(symbol_query),
            gene_summary=self.gene_collection.find_one(symbol_query),
        )

    def get_gene_records(self, genes: list[str]) -> dict[str, dict[str, Any]]:
        """Return public OncoKB cancer-gene markers keyed by symbol."""
        normalized = sorted({str(gene).strip() for gene in genes if str(gene).strip()})
        if not normalized:
            return {}
        symbol_query = {
            "$or": [
                {"gene": {"$in": normalized}},
                {"previous_symbols": {"$in": normalized}},
                {"alias_symbols": {"$in": normalized}},
            ]
        }
        action_rows = self.cancer_gene_collection.find(symbol_query)
        summary_rows = list(self.gene_collection.find(symbol_query))
        summary_by_symbol: dict[str, dict[str, Any]] = {}
        for row in summary_rows:
            approved = str(row.get("gene") or "").strip()
            symbols = (
                [approved]
                + _as_symbol_list(row.get("previous_symbols"))
                + _as_symbol_list(row.get("alias_symbols"))
            )
            for symbol in symbols:
                if symbol:
                    summary_by_symbol[symbol] = row
        records: dict[str, dict[str, Any]] = {}
        for row in action_rows:
            approved = str(row.get("gene") or "").strip()
            summary = summary_by_symbol.get(approved)
            merged = _merge_public_gene_records(cancer_gene=row, gene_summary=summary) or row
            if approved:
                records[approved] = merged
            for requested in normalized:
                aliases = set(_as_symbol_list(row.get("previous_symbols"))) | set(
                    _as_symbol_list(row.get("alias_symbols"))
                )
                if requested == approved or requested in aliases:
                    records[requested] = merged
        missing = [gene for gene in normalized if gene not in records]
        if missing:
            rows = self.gene_collection.find(
                {
                    "$or": [
                        {"gene": {"$in": missing}},
                        {"previous_symbols": {"$in": missing}},
                        {"alias_symbols": {"$in": missing}},
                    ]
                }
            )
            records.update({str(row.get("gene")): row for row in rows if row.get("gene")})
        return records
