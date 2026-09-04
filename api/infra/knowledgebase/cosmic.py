"""Bounded read access to the licensed COSMIC knowledgebase collections."""

from __future__ import annotations

import re
import time
from typing import Any

from api.infra.mongo.repositories.base import BaseRepository

_LOCUS_PATTERN = re.compile(r"(?:chr)?([0-9XYM]+)[:_]([0-9]+)", re.IGNORECASE)
_RESULT_LIMIT = 50
_AVAILABILITY_TTL_SECONDS = 30.0
_PRODUCT_COLLECTION_ATTRS = {
    "actionability": "cosmic_actionability_collection",
    "breakpoints": "cosmic_breakpoints_collection",
    "cancer_gene_census": "cosmic_cgc_collection",
    "census_gene_mutations": "cosmic_mutant_census_collection",
    "cgc_hallmarks": "cosmic_cgc_hallmarks_collection",
    "copy_number": "cosmic_cna_collection",
    "classifications": "cosmic_classification_collection",
    "fusions": "cosmic_fusion_collection",
    "mutation_census": "cosmic_mutation_census_collection",
    "resistance_mutations": "cosmic_resistance_collection",
    "structural_variants": "cosmic_structural_collection",
    "targeted_variants": "cosmic_targeted_collection",
}


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
        self._availability_cache: dict[str, tuple[float, bool]] = {}

    def ensure_indexes(self) -> None:
        """Index an installed optional genome-screen collection without creating it."""
        collection = self.get_collection()
        database = getattr(self.adapter, "knowledgebase_db", None)
        if database is not None and collection.name not in database.list_collection_names():
            return
        collection.create_index(
            [("chr", 1), ("start", 1), ("ref", 1), ("alt", 1)],
            name="genomic_variant",
            background=True,
        )

    @staticmethod
    def _rows(cursor: Any) -> list[dict[str, Any]]:
        return [{key: value for key, value in row.items() if key != "_id"} for row in cursor]

    def _availability(self, products: list[str]) -> dict[str, bool]:
        versions = getattr(self.adapter, "knowledgebase_versions_collection", None)
        if versions is None:
            return {product: False for product in products}
        now = time.monotonic()
        expired = [
            product
            for product in products
            if product not in self._availability_cache
            or now - self._availability_cache[product][0] >= _AVAILABILITY_TTL_SECONDS
        ]
        sources = [f"cosmic_{product}" for product in expired]
        active = {
            str(row["source"])
            for row in versions.find(
                {"source": {"$in": sources}, "status": "active"}, {"_id": 0, "source": 1}
            )
            if row.get("source")
        }
        for product in expired:
            collection_attr = _PRODUCT_COLLECTION_ATTRS[product]
            collection = getattr(self.adapter, collection_attr, None)
            available = (
                f"cosmic_{product}" in active
                and collection is not None
                and collection.estimated_document_count() > 0
            )
            self._availability_cache[product] = (now, available)
        return {product: self._availability_cache[product][1] for product in products}

    def _gene_census(self, genes: list[str]) -> list[dict[str, Any]]:
        collection = getattr(self.adapter, "cosmic_cgc_collection", None)
        if collection is None or not genes:
            return []
        projection = {
            "_id": 0,
            "gene_symbol": 1,
            "cosmic_gene_id": 1,
            "name": 1,
            "somatic": 1,
            "germline": 1,
            "tumour_types_somatic": 1,
            "tumour_types_germline": 1,
            "cancer_syndrome": 1,
            "molecular_genetics": 1,
            "role_in_cancer": 1,
            "mutation_types": 1,
            "translocation_partner": 1,
            "tier": 1,
        }
        return self._rows(collection.find({"gene_symbol": {"$in": genes}}, projection).limit(25))

    def get_cancer_gene_census_records(self, genes: list[str]) -> dict[str, dict[str, Any]]:
        """Return Cancer Gene Census marker records keyed by requested gene symbol."""
        normalized = list(
            dict.fromkeys(str(gene).strip().upper() for gene in genes if str(gene).strip())
        )
        collection = getattr(self.adapter, "cosmic_cgc_collection", None)
        if collection is None or not normalized:
            return {}
        projection = {
            "_id": 0,
            "gene_symbol": 1,
            "cosmic_gene_id": 1,
            "name": 1,
            "somatic": 1,
            "germline": 1,
            "role_in_cancer": 1,
            "mutation_types": 1,
            "tier": 1,
        }
        records = self._rows(collection.find({"gene_symbol": {"$in": normalized}}, projection))
        return {
            str(record["gene_symbol"]).upper(): record
            for record in records
            if record.get("gene_symbol")
        }

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

    def get_gene_evidence(self, gene: str) -> dict[str, Any]:
        """Return bounded Cancer Gene Census context for one approved gene symbol."""
        genes = _gene_symbols([gene])
        return {
            "gene_census": self._gene_census(genes),
            "hallmarks": self._hallmarks(genes),
            "availability": self._availability(["cancer_gene_census", "cgc_hallmarks"]),
        }

    def _actionability(self, genes: list[str]) -> list[dict[str, Any]]:
        collection = getattr(self.adapter, "cosmic_actionability_collection", None)
        if collection is None:
            return []
        if not genes:
            return []
        projection = {
            "_id": 0,
            "genes": 1,
            "mutation_remark": 1,
            "mutation_selectivity": 1,
            "disease": 1,
            "actionability_rank": 1,
            "actionability_rank_description": 1,
            "development_status": 1,
            "drug_combination": 1,
            "testing_required": 1,
            "trial_id": 1,
            "trial_status": 1,
            "source_type": 1,
            "source": 1,
            "trial_outcome": 1,
        }
        query = {"genes": {"$all": genes[:2]}} if len(genes) > 1 else {"genes": genes[0]}
        return self._rows(collection.find(query, projection).limit(25))

    def _classifications(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Resolve bounded phenotype labels referenced by matched COSMIC records."""
        phenotype_ids = list(
            dict.fromkeys(
                str(phenotype_id)
                for record in records
                for phenotype_id in [
                    record.get("cosmic_phenotype_id"),
                    *(record.get("cosmic_phenotype_ids") or []),
                ]
                if phenotype_id
            )
        )[:_RESULT_LIMIT]
        collection = getattr(self.adapter, "cosmic_classification_collection", None)
        if collection is None or not phenotype_ids:
            return []
        return self._rows(
            collection.find(
                {"cosmic_phenotype_id": {"$in": phenotype_ids}},
                {
                    "_id": 0,
                    "cosmic_phenotype_id": 1,
                    "primary_site": 1,
                    "primary_histology": 1,
                    "histology_subtype_1": 1,
                    "histology_subtype_2": 1,
                    "nci_code": 1,
                    "efo": 1,
                },
            ).limit(_RESULT_LIMIT)
        )

    def _resistance(self, mutation_ids: list[str]) -> list[dict[str, Any]]:
        collection = getattr(self.adapter, "cosmic_resistance_collection", None)
        if collection is None or not mutation_ids:
            return []
        projection = {
            "_id": 0,
            "genomic_mutation_id": 1,
            "gene_symbol": 1,
            "drug_name": 1,
            "drug_response": 1,
            "mutation_aa": 1,
            "mutation_cds": 1,
            "hgvsp": 1,
            "hgvsc": 1,
            "pubmed_pmid": 1,
        }
        return self._rows(
            collection.find({"genomic_mutation_id": {"$in": mutation_ids}}, projection).limit(25)
        )

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
        variant_projection = {
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
        genome = (
            self._rows(
                self.get_collection()
                .find({"$or": clauses}, variant_projection)
                .limit(_RESULT_LIMIT)
            )
            if clauses
            else []
        )
        noncoding_collection = getattr(self.adapter, "cosmic_noncoding_collection", None)
        noncoding = (
            self._rows(
                noncoding_collection.find({"$or": clauses}, variant_projection).limit(_RESULT_LIMIT)
            )
            if noncoding_collection is not None and clauses
            else []
        )
        targeted_collection = getattr(self.adapter, "cosmic_targeted_collection", None)
        targeted = (
            self._rows(
                targeted_collection.find({"$or": clauses}, variant_projection).limit(_RESULT_LIMIT)
            )
            if targeted_collection is not None and clauses
            else []
        )
        mutant_census_collection = getattr(self.adapter, "cosmic_mutant_census_collection", None)
        mutant_census_clauses: list[dict[str, Any]] = []
        try:
            mutant_census_clauses.append(
                {
                    "chromosome": {"$in": _chromosome_values(variant.get("CHROM"))},
                    "genome_start": int(variant.get("POS")),
                    "genomic_wt_allele": variant.get("REF"),
                    "genomic_mut_allele": variant.get("ALT"),
                }
            )
        except (TypeError, ValueError):
            pass
        if identifiers:
            mutant_census_clauses.append({"genomic_mutation_id": {"$in": identifiers}})
        mutant_census_projection = {
            "_id": 0,
            "genomic_mutation_id": 1,
            "legacy_mutation_id": 1,
            "gene_symbol": 1,
            "transcript_accession": 1,
            "mutation_cds": 1,
            "mutation_aa": 1,
            "mutation_description": 1,
            "hgvsp": 1,
            "hgvsc": 1,
            "hgvsg": 1,
            "mutation_somatic_status": 1,
            "cosmic_phenotype_id": 1,
            "pubmed_pmid": 1,
        }
        mutant_census = (
            self._rows(
                mutant_census_collection.find(
                    {"$or": mutant_census_clauses}, mutant_census_projection
                ).limit(_RESULT_LIMIT)
            )
            if mutant_census_collection is not None and mutant_census_clauses
            else []
        )

        chromosome = _chromosome_values(variant.get("CHROM"))
        position = variant.get("POS")
        ref = variant.get("REF")
        alt = variant.get("ALT")
        cmc_clauses: list[dict[str, Any]] = []
        try:
            cmc_clauses.append(
                {
                    "chr_grch38": {"$in": chromosome},
                    "start_grch38": int(position),
                    "ref": ref,
                    "alt": alt,
                }
            )
        except (TypeError, ValueError):
            pass
        if identifiers:
            cmc_clauses.append({"genomic_mutation_id": {"$in": identifiers}})
        cmc_collection = getattr(self.adapter, "cosmic_mutation_census_collection", None)
        cmc_projection = {
            "_id": 0,
            "genomic_mutation_id": 1,
            "legacy_mutation_id": 1,
            "gene_name": 1,
            "accession_number": 1,
            "mutation_cds": 1,
            "mutation_aa": 1,
            "mutation_description_aa": 1,
            "cosmic_sample_tested": 1,
            "cosmic_sample_mutated": 1,
            "disease": 1,
            "wgs_disease": 1,
            "clinvar_clnsig": 1,
            "mutation_significance_tier": 1,
        }
        census = (
            self._rows(
                cmc_collection.find({"$or": cmc_clauses}, cmc_projection).limit(_RESULT_LIMIT)
            )
            if cmc_collection is not None and cmc_clauses
            else []
        )
        for row in genome:
            row["source_product"] = "Genome screens"
        for row in noncoding:
            row["source_product"] = "Non-coding variants"
        for row in targeted:
            row["source_product"] = "Targeted screens"
        for row in mutant_census:
            row["source_product"] = "Census gene mutations"
            row["id"] = row.get("genomic_mutation_id")
            row["gene"] = row.get("gene_symbol")
        for row in census:
            row["source_product"] = "Mutation Census"
            row["id"] = row.get("genomic_mutation_id")
            row["gene"] = row.get("gene_name")
            row["hgvsp"] = row.get("mutation_aa")
            row["hgvsc"] = row.get("mutation_cds")
        matched_ids = list(
            dict.fromkeys(
                identifiers
                + [
                    str(row["id"])
                    for row in genome + noncoding + targeted + mutant_census + census
                    if row.get("id")
                ]
            )
        )
        genes = _gene_symbols([csq.get("SYMBOL")])
        return {
            "kind": "small_variant",
            "match_count": (
                len(genome) + len(noncoding) + len(targeted) + len(mutant_census) + len(census)
            ),
            "cosmic_ids": matched_ids,
            "records": census + targeted + mutant_census + genome + noncoding,
            "classifications": self._classifications(mutant_census),
            "gene_census": self._gene_census(genes),
            "hallmarks": self._hallmarks(genes),
            "resistance": self._resistance(matched_ids),
            "actionability": self._actionability(genes),
            "availability": self._availability(
                [
                    "mutation_census",
                    "targeted_variants",
                    "census_gene_mutations",
                    "classifications",
                    "cancer_gene_census",
                    "cgc_hallmarks",
                    "resistance_mutations",
                    "actionability",
                ]
            ),
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
                        "cosmic_phenotype_ids": {"$addToSet": "$cosmic_phenotype_id"},
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
                    "cosmic_phenotype_ids": [
                        value for value in row.get("cosmic_phenotype_ids", []) if value
                    ][:_RESULT_LIMIT],
                }
                for row in collection.aggregate(pipeline, allowDiskUse=False)
            ]
        return {
            "kind": "copy_number",
            "match_count": sum(int(row["observations"]) for row in records),
            "records": records,
            "classifications": self._classifications(records),
            "gene_census": self._gene_census(genes),
            "hallmarks": self._hallmarks(genes),
            "actionability": self._actionability(genes),
            "availability": self._availability(
                ["copy_number", "classifications", "cancer_gene_census", "cgc_hallmarks"]
            ),
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
                "cosmic_phenotype_id": 1,
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
            "classifications": self._classifications(records),
            "gene_census": self._gene_census(genes),
            "hallmarks": self._hallmarks(genes),
            "actionability": self._actionability(genes),
            "availability": self._availability(
                [
                    "fusions",
                    "classifications",
                    "cancer_gene_census",
                    "cgc_hallmarks",
                    "actionability",
                ]
            ),
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
                "cosmic_phenotype_id": 1,
            }
            records = self._rows(collection.find({"$or": clauses}, projection).limit(_RESULT_LIMIT))
        structural_ids = [
            str(row["cosmic_structural_id"]) for row in records if row.get("cosmic_structural_id")
        ]
        structural_collection = getattr(self.adapter, "cosmic_structural_collection", None)
        structural = []
        if structural_collection is not None and structural_ids:
            structural = self._rows(
                structural_collection.find(
                    {"cosmic_structural_id": {"$in": structural_ids}},
                    {
                        "_id": 0,
                        "cosmic_structural_id": 1,
                        "mutation_type": 1,
                        "description": 1,
                        "chromosome_from": 1,
                        "chromosome_to": 1,
                        "location_from_min": 1,
                        "location_to_min": 1,
                        "pubmed_pmid": 1,
                        "cosmic_phenotype_id": 1,
                    },
                ).limit(_RESULT_LIMIT)
            )
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
            "structural_variants": structural,
            "classifications": self._classifications(records + structural),
            "gene_census": self._gene_census(genes),
            "hallmarks": self._hallmarks(genes),
            "actionability": self._actionability(genes),
            "availability": self._availability(
                [
                    "breakpoints",
                    "structural_variants",
                    "classifications",
                    "cancer_gene_census",
                    "cgc_hallmarks",
                ]
            ),
        }
