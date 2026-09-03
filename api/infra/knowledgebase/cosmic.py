"""Bounded read access to the licensed COSMIC knowledgebase collections."""

from __future__ import annotations

import re
from typing import Any

from api.infra.mongo.repositories.base import BaseRepository

_LOCUS_PATTERN = re.compile(r"(?:chr)?([0-9XYM]+)[:_]([0-9]+)", re.IGNORECASE)
_RESULT_LIMIT = 50


def _chromosome_values(value: Any) -> list[str]:
    chromosome = str(value or "").removeprefix("chr").removeprefix("CHR")
    return list(dict.fromkeys(filter(None, (chromosome, f"chr{chromosome}"))))


def _gene_symbols(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    symbols = []
    for value in values:
        symbol = (value.get("gene") or value.get("name")) if isinstance(value, dict) else value
        if symbol:
            symbols.append(str(symbol).upper())
    return list(dict.fromkeys(symbols))[:50]


class CosmicRepository(BaseRepository):
    """Query COSMIC by indexed finding identity without exposing source sample data."""

    def __init__(self, adapter: Any) -> None:
        super().__init__(adapter)
        self.set_collection(self.adapter.cosmic_collection)

    def ensure_indexes(self) -> None:
        """Create the exact genomic lookup index used by the detail page."""
        self.get_collection().create_index(
            [("chr", 1), ("start", 1), ("ref", 1), ("alt", 1)],
            name="genomic_variant",
            background=True,
        )

    @staticmethod
    def _rows(cursor: Any) -> list[dict[str, Any]]:
        return [{key: value for key, value in row.items() if key != "_id"} for row in cursor]

    def _hallmarks(self, genes: list[str]) -> list[dict[str, Any]]:
        collection = getattr(self.adapter, "cosmic_cgc_hallmarks_collection", None)
        if collection is None or not genes:
            return []
        projection = {
            "_id": 0,
            "gene_symbol": 1,
            "cosmic_gene_id": 1,
            "hallmark": 1,
            "impact": 1,
            "description": 1,
            "pubmed_pmid": 1,
        }
        return self._rows(collection.find({"gene_symbol": {"$in": genes}}, projection).limit(25))

    def _actionability(
        self, *, mutation_ids: list[str] | None = None, fusion_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        collection = getattr(self.adapter, "cosmic_actionability_collection", None)
        if collection is None:
            return []
        clauses = []
        if mutation_ids:
            clauses.append({"genomic_mutation_id": {"$in": mutation_ids}})
        if fusion_ids:
            normalized = list(
                dict.fromkeys(fusion_ids + [value.removeprefix("COSF") for value in fusion_ids])
            )
            clauses.append({"fusion_id": {"$in": normalized}})
        if not clauses:
            return []
        projection = {
            "_id": 0,
            "genomic_mutation_id": 1,
            "fusion_id": 1,
            "disease": 1,
            "drug_name": 1,
            "drug": 1,
            "rank": 1,
            "evidence_type": 1,
            "clinical_trial": 1,
            "pubmed_pmid": 1,
        }
        return self._rows(collection.find({"$or": clauses}, projection).limit(25))

    def get_variant_evidence(self, variant: dict[str, Any]) -> dict[str, Any]:
        """Return exact genomic COSMIC matches and gene-level context for an SNV/indel."""
        info = variant.get("INFO") if isinstance(variant.get("INFO"), dict) else {}
        csq = info.get("selected_CSQ") if isinstance(info.get("selected_CSQ"), dict) else {}
        identifiers = [str(value) for value in variant.get("cosmic_ids") or [] if value]
        clauses: list[dict[str, Any]] = []
        try:
            clauses.append(
                {
                    "chr": {"$in": _chromosome_values(variant.get("CHROM"))},
                    "start": int(variant.get("POS")),
                    "ref": variant.get("REF"),
                    "alt": variant.get("ALT"),
                }
            )
        except (TypeError, ValueError):
            pass
        if identifiers:
            clauses.append({"id": {"$in": identifiers}})
        projection = {
            "_id": 0,
            "id": 1,
            "legacy_id": 1,
            "gene": 1,
            "transcript": 1,
            "hgvsc": 1,
            "hgvsp": 1,
            "hgvsg": 1,
            "so_term": 1,
            "tier": 1,
            "cnt": 1,
        }
        coding = (
            self._rows(
                self.get_collection().find({"$or": clauses}, projection).limit(_RESULT_LIMIT)
            )
            if clauses
            else []
        )
        noncoding_collection = getattr(self.adapter, "cosmic_noncoding_collection", None)
        noncoding = (
            self._rows(noncoding_collection.find({"$or": clauses}, projection).limit(_RESULT_LIMIT))
            if noncoding_collection is not None and clauses
            else []
        )
        matched_ids = list(
            dict.fromkeys(
                identifiers + [str(row["id"]) for row in coding + noncoding if row.get("id")]
            )
        )
        genes = _gene_symbols([csq.get("SYMBOL")])
        return {
            "kind": "small_variant",
            "match_count": len(coding) + len(noncoding),
            "cosmic_ids": matched_ids,
            "records": coding + noncoding,
            "hallmarks": self._hallmarks(genes),
            "actionability": self._actionability(mutation_ids=matched_ids),
        }

    def get_cnv_evidence(self, cnv: dict[str, Any]) -> dict[str, Any]:
        """Return bounded COSMIC CNA summaries overlapping the reported interval."""
        genes = _gene_symbols(cnv.get("genes"))
        collection = getattr(self.adapter, "cosmic_cna_collection", None)
        records: list[dict[str, Any]] = []
        chromosome = cnv.get("chr") or cnv.get("CHROM")
        start = cnv.get("start") or cnv.get("POS")
        end = cnv.get("end") or (cnv.get("INFO") or {}).get("END")
        try:
            interval_query: dict[str, Any] | None = {
                "chromosome": {"$in": _chromosome_values(chromosome)},
                "genome_start": {"$lte": int(end)},
                "genome_stop": {"$gte": int(start)},
            }
        except (TypeError, ValueError):
            interval_query = None
        if interval_query is not None and genes:
            interval_query["gene_symbol"] = {"$in": genes}
        if collection is not None and interval_query is not None:
            pipeline = [
                {"$match": interval_query},
                {
                    "$group": {
                        "_id": {"gene": "$gene_symbol", "type": "$mut_type"},
                        "observations": {"$sum": 1},
                        "cosmic_ids": {"$addToSet": "$cosmic_cnv_id"},
                    }
                },
                {"$sort": {"observations": -1}},
                {"$limit": _RESULT_LIMIT},
            ]
            records = [
                {
                    "gene": row.get("_id", {}).get("gene"),
                    "type": row.get("_id", {}).get("type"),
                    "observations": row.get("observations", 0),
                    "cosmic_ids": [value for value in row.get("cosmic_ids", []) if value][:10],
                }
                for row in collection.aggregate(pipeline, allowDiskUse=False)
            ]
        return {
            "kind": "copy_number",
            "match_count": sum(int(row["observations"]) for row in records),
            "records": records,
            "hallmarks": self._hallmarks(genes),
            "actionability": [],
        }

    def get_fusion_evidence(self, fusion: dict[str, Any]) -> dict[str, Any]:
        """Return exact COSMIC fusion-partner matches."""
        calls = fusion.get("fusion") if isinstance(fusion.get("fusion"), list) else []
        call = calls[0] if calls else {}
        genes = _gene_symbols(
            [call.get("gene1"), call.get("gene2"), fusion.get("gene1"), fusion.get("gene2")]
        )
        collection = getattr(self.adapter, "cosmic_fusion_collection", None)
        records = []
        if collection is not None and len(genes) >= 2:
            query = {
                "$or": [
                    {"five_prime_gene_symbol": genes[0], "three_prime_gene_symbol": genes[1]},
                    {"five_prime_gene_symbol": genes[1], "three_prime_gene_symbol": genes[0]},
                ]
            }
            projection = {
                "_id": 0,
                "cosmic_fusion_id": 1,
                "five_prime_gene_symbol": 1,
                "three_prime_gene_symbol": 1,
                "mutation_type": 1,
                "primary_histology": 1,
                "pubmed_pmid": 1,
            }
            records = self._rows(collection.find(query, projection).limit(_RESULT_LIMIT))
        ids = list(
            dict.fromkeys(
                str(row["cosmic_fusion_id"]) for row in records if row.get("cosmic_fusion_id")
            )
        )
        return {
            "kind": "fusion",
            "match_count": len(records),
            "cosmic_ids": ids,
            "records": records,
            "hallmarks": self._hallmarks(genes),
            "actionability": self._actionability(fusion_ids=ids),
        }

    def get_translocation_evidence(self, translocation: dict[str, Any]) -> dict[str, Any]:
        """Return COSMIC breakpoint records overlapping the reported breakends."""
        loci: list[tuple[str, int]] = []
        for value in (
            translocation.get("positions"),
            translocation.get("breakpoints"),
            translocation.get("POS"),
        ):
            for match in _LOCUS_PATTERN.finditer(str(value or "")):
                loci.append((match.group(1), int(match.group(2))))
        collection = getattr(self.adapter, "cosmic_breakpoints_collection", None)
        records = []
        if collection is not None and loci:
            clauses = []
            for chromosome, position in loci[:2]:
                chromosomes = _chromosome_values(chromosome)
                clauses.extend(
                    [
                        {
                            "chrom_from": {"$in": chromosomes},
                            "location_from_min": {"$lte": position},
                            "location_from_max": {"$gte": position},
                        },
                        {
                            "chrom_to": {"$in": chromosomes},
                            "location_to_min": {"$lte": position},
                            "location_to_max": {"$gte": position},
                        },
                    ]
                )
            projection = {
                "_id": 0,
                "cosmic_structural_id": 1,
                "mutation_type": 1,
                "chrom_from": 1,
                "location_from_min": 1,
                "chrom_to": 1,
                "location_to_min": 1,
                "pubmed_pmid": 1,
            }
            records = self._rows(collection.find({"$or": clauses}, projection).limit(_RESULT_LIMIT))
        genes = _gene_symbols(translocation.get("genes") or [])
        return {
            "kind": "translocation",
            "match_count": len(records),
            "cosmic_ids": list(
                dict.fromkeys(
                    str(row["cosmic_structural_id"])
                    for row in records
                    if row.get("cosmic_structural_id")
                )
            ),
            "records": records,
            "hallmarks": self._hallmarks(genes),
            "actionability": [],
        }
