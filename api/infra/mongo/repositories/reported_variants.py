"""
ReportedVariantsRepository module for Coyote3
=========================================

This module defines the `ReportedVariantsRepository` class used for accessing and managing
**reported clinical finding snapshots** in MongoDB.

A record represents one typed clinical finding included in a generated report
for a sample, with its report-time interpretation (an immutable snapshot).

Collection purpose
------------------
- Persist per-report, per-sample typed finding snapshots (audit-safe)
- Enable fast lookups for:
  - "Which variants were reported in report X for sample Y?"
  - "How many times was variant/simple_id reported, and at which tiers?"
  - "Which samples/reports included a given gene / HGVSp / HGVSc?"

"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from typing import Any, Dict, List

from pymongo import ASCENDING, DESCENDING, UpdateOne

from api.contracts.operations import OperationResult
from api.domain.core.dna.variant_identity import build_simple_id_hash_from_simple_id
from api.infra.mongo.repositories.base import BaseRepository


def _reported_variant_search_query(
    *,
    search_str: str,
    search_mode: str,
    asp_ids: list | None = None,
) -> dict[str, Any] | None:
    """Build the reported-variant snapshot search query."""
    if not search_str:
        return None

    regex = {"$regex": search_str, "$options": "i"}
    mode = str(search_mode or "variant").lower()
    variant_fields = [
        "variant",
        "hgvsp",
        "hgvsc",
        "genomic",
        "simple_id",
        "simple_id_hash",
    ]

    if mode == "gene":
        query: dict[str, Any] = {
            "$or": [
                {"gene": regex},
                {"genes": regex},
                {"gene1": regex},
                {"gene2": regex},
            ]
        }
    elif mode == "transcript":
        query = {
            "$or": [
                {"transcript": regex},
            ]
        }
    elif mode == "hgvsp":
        query = {
            "$or": [
                {"hgvsp": regex},
            ]
        }
    elif mode == "hgvsc":
        query = {
            "$or": [
                {"hgvsc": regex},
            ]
        }
    elif mode == "genomic":
        query = {
            "$or": [
                {"simple_id": regex},
                {"simple_id_hash": regex},
                {"variant": regex},
                {"genomic": regex},
            ]
        }
    elif mode == "nomenclature":
        query = {"nomenclature": regex}
    elif mode == "variant":
        query = {"$or": [{field: regex} for field in variant_fields]}
    elif mode == "author":
        query = {"created_by": regex}
    elif mode == "subpanel":
        query = {"subpanel": regex}
    elif mode == "all":
        query = {
            "$or": [
                {"gene": regex},
                {"genes": regex},
                {"gene1": regex},
                {"gene2": regex},
                {"transcript": regex},
                {"created_by": regex},
                {"subpanel": regex},
                *[{field: regex} for field in variant_fields],
            ]
        }
    elif mode == "annotation":
        return None
    else:
        return None

    if asp_ids:
        return {
            "$and": [
                query,
                {
                    "$or": [
                        {"assay": {"$in": asp_ids}},
                        {"assay_group": {"$in": asp_ids}},
                    ]
                },
            ]
        }
    return query


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class ReportedVariantsRepository(BaseRepository):
    """
    MongoDB handler for typed report finding snapshots.

    The `ReportedVariantsRepository` provides a focused interface for interacting with the
    `reported_variants` collection. Each document in the collection corresponds to a
    single finding reported in a specific report for a specific sample.

    Notes
    -----
    - Documents are written once at report creation time.
    - Snapshot fields (e.g. `tier`) should NOT be retroactively updated when global
      tier annotations change.
    - Sample metadata remains in `samples` and full variant payload remains in `variants`.
      This collection stores identifiers + snapshot tier + small query helper fields.
    """

    def __init__(self, adapter: Any):
        """
        Initialize the repository with a given adapter and bind the collection.
        """
        super().__init__(adapter)

        # Bind the Mongo collection holding per-report reported variant snapshots.
        # Prefer an explicit adapter attribute (e.g., adapter.reported_variants_collection).
        # If your adapter uses a different naming convention, update this accordingly.
        self.set_collection(self.adapter.reported_variants_collection)

    def bulk_upsert_from_snapshot_rows(
        self,
        sample_name,
        sample_oid,
        report_oid,
        report_id: str,
        snapshot_rows: List[Dict[str, Any]],
        created_by: str,
        report_num: int | None = None,
    ) -> int:
        """
        Upsert reported variant snapshot rows for a single report.

        Each row must contain ``analysis_type``, ``simple_id``,
        ``simple_id_hash``, and ``created_on``. Finding-specific fields remain
        typed by the report workflow.

        This method writes only after the report is saved successfully.
        """
        if not snapshot_rows:
            return 0

        _col = self.get_collection()
        ops = []

        for r in snapshot_rows:
            simple_id = r.get("simple_id")
            if not simple_id:
                continue
            simple_id_hash = r.get("simple_id_hash") or build_simple_id_hash_from_simple_id(
                simple_id
            )

            # Ensure core fields are always set (don’t rely on snapshot_rows to be perfect)
            doc = {
                "sample_name": sample_name,
                "sample_oid": sample_oid,
                "report_oid": report_oid,
                "report_id": report_id,
                "report_num": report_num,
                "created_by": created_by,
                **r,  # r can include var_oid, tier, gene, etc.
            }
            doc["simple_id_hash"] = simple_id_hash

            # IMPORTANT: do NOT allow snapshot_rows to override report_oid/report_id/sample_oid
            doc["sample_name"] = sample_name
            doc["sample_oid"] = sample_oid
            doc["report_oid"] = report_oid
            doc["report_id"] = report_id
            doc["report_num"] = report_num
            doc["created_by"] = created_by

            ops.append(
                UpdateOne(
                    {
                        "sample_oid": sample_oid,
                        "report_oid": report_oid,
                        "simple_id": simple_id,
                    },
                    {"$setOnInsert": doc},
                    upsert=True,
                )
            )

        if not ops:
            return 0

        res = self.get_collection().bulk_write(ops, ordered=False)
        return int(res.upserted_count or 0)

    def list_reported_variants(self, query: dict) -> list:
        """
        List reported variant snapshot documents matching the given Mongo query.
        """
        return list(self.get_collection().find(query).sort("time_created", -1))

    def delete_sample_reported_variants(self, sample_oid) -> OperationResult:
        """Delete immutable report snapshots owned by a deleted sample."""
        return OperationResult.from_delete(
            self.get_collection().delete_many({"sample_oid": sample_oid})
        )

    def find_reported_variants_by_search_string(
        self,
        *,
        search_str: str,
        search_mode: str,
        asp_ids: list | None = None,
        limit: int | None = None,
    ) -> list:
        """Search reported variant snapshots by normalized report-time fields."""
        query = _reported_variant_search_query(
            search_str=search_str,
            search_mode=search_mode,
            asp_ids=asp_ids,
        )
        if query is None:
            return []

        cursor = self.get_collection().find(query).sort("time_created", -1)
        if limit is not None:
            cursor = cursor.limit(limit)
        return list(cursor)

    def get_reported_docs(self, query: dict, limit: int | None = None) -> list:
        """
        Retrieve reported variant documents based on the provided query.

        Args:
            query (dict): MongoDB query to filter reported variant documents.
            limit (Optional[int]): Maximum number of documents to retrieve. If None, retrieves all matching documents.
            include_annotation_text (bool): Whether to include documents with annotation text.

        Returns:
            list: List of reported variant documents matching the query.
        """
        if not query:
            return []

        cursor = (
            self.get_collection().find(query, {"_id": 1, "sample_oid": 1}).sort("time_created", -1)
        )

        if limit is not None:
            cursor = cursor.limit(limit)

        return list(cursor)

    def ensure_indexes(self) -> None:
        """
        Create required indexes for the reported_variants collection.

        Safe to call multiple times; MongoDB will keep existing indexes.
        The operation is idempotent; MongoDB preserves matching indexes.
        """
        col = self.get_collection()
        col.create_index(
            [("reported_variant_id", ASCENDING)],
            name="reported_variant_id_1",
            unique=True,
            background=True,
            partialFilterExpression={"reported_variant_id": {"$exists": True, "$type": "string"}},
        )

        # Prevent duplicates: same variant cannot be recorded twice in the same report
        col.create_index(
            [("genes", ASCENDING), ("tier", ASCENDING)],
            name="ix_genes_tier",
            background=True,
        )
        col.create_index(
            [
                ("sample_oid", ASCENDING),
                ("report_oid", ASCENDING),
                ("simple_id", ASCENDING),
            ],
            unique=True,
            name="uq_sample_report_simple_id",
            background=True,
        )

        # Fast "open report": fetch typed findings for a given sample and report.
        col.create_index(
            [
                ("sample_oid", ASCENDING),
                ("report_oid", ASCENDING),
                ("analysis_type", ASCENDING),
            ],
            name="ix_sample_report_analysis_type",
            background=True,
        )

        # Fast reported-variant detail lookup:
        # query = {"gene": gene, "$or": [{"simple_id_hash": ..., "simple_id": ...}]}
        col.create_index(
            [("gene", ASCENDING), ("simple_id_hash", ASCENDING), ("simple_id", ASCENDING)],
            name="ix_gene_simple_id_hash_simple_id",
            background=True,
            partialFilterExpression={
                "gene": {"$exists": True, "$type": "string"},
                "simple_id_hash": {"$exists": True, "$type": "string"},
                "simple_id": {"$exists": True, "$type": "string"},
            },
        )
        col.create_index(
            [("gene", ASCENDING), ("simple_id_hash", ASCENDING), ("simple_id", ASCENDING)],
            name="ix_gene_simple_id_hash_simple_id_lookup",
            background=True,
        )

        # Cross-sample variant queries by genomic identity + tier
        col.create_index(
            [("simple_id_hash", ASCENDING), ("simple_id", ASCENDING), ("tier", ASCENDING)],
            name="ix_simple_id_hash_simple_id_tier",
            background=True,
        )

        # Protein / transcript queries (tier distribution, most common, etc.)
        col.create_index(
            [("gene", ASCENDING), ("hgvsp", ASCENDING), ("tier", ASCENDING)],
            name="ix_gene_hgvsp_tier",
            background=True,
        )
        col.create_index(
            [("gene", ASCENDING), ("hgvsc", ASCENDING), ("tier", ASCENDING)],
            name="ix_gene_hgvsc_tier",
            background=True,
        )
        col.create_index(
            [("gene1", ASCENDING), ("tier", ASCENDING)],
            name="ix_gene1_tier",
            background=True,
        )
        col.create_index(
            [("gene2", ASCENDING), ("tier", ASCENDING)],
            name="ix_gene2_tier",
            background=True,
        )
        col.create_index(
            [("nomenclature", ASCENDING), ("analysis_type", ASCENDING), ("tier", ASCENDING)],
            name="ix_nomenclature_analysis_type_tier",
            background=True,
        )

        # Optional: time-based queries (recent reports, time-window stats)
        col.create_index(
            [("created_on", DESCENDING)],
            name="ix_created_on_desc",
            background=True,
        )
        col.create_index(
            [("time_created", DESCENDING)],
            name="ix_time_created_desc",
            background=True,
        )

        col.create_index(
            [("tier", ASCENDING)],
            name="ix_tier",
            background=True,
        )
        col.create_index(
            [("assay", ASCENDING), ("tier", ASCENDING)],
            name="ix_assay_tier",
            background=True,
        )
        col.create_index(
            [
                ("gene", ASCENDING),
                ("report_oid", ASCENDING),
                ("tier", ASCENDING),
                ("assay", ASCENDING),
            ],
            name="ix_gene_report_tier_assay",
            background=True,
        )
        col.create_index(
            [
                ("gene", ASCENDING),
                ("sample_oid", ASCENDING),
                ("tier", ASCENDING),
                ("assay", ASCENDING),
            ],
            name="ix_gene_sample_tier_assay",
            background=True,
        )
        col.create_index(
            [
                ("gene", ASCENDING),
                ("sample_name", ASCENDING),
                ("tier", ASCENDING),
                ("assay", ASCENDING),
            ],
            name="ix_gene_sample_name_tier_assay",
            background=True,
        )

    def get_gene_cohort_findings(
        self,
        *,
        gene: str,
        asp_ids: list[str] | None,
        report_oids: list[Any] | None = None,
        sample_oids: list[Any] | None = None,
        sample_names: list[str] | None = None,
        limit: int = 10_000,
    ) -> list[dict[str, Any]]:
        """Return bounded report snapshots for exact reports or profiled samples."""
        query_parts: list[dict[str, Any]] = [
            {
                "$or": [
                    {"gene": gene},
                    {"genes": gene},
                    {"gene1": gene},
                    {"gene2": gene},
                ]
            },
            {"tier": {"$in": [1, 2, 3, 4]}},
        ]
        if report_oids is not None:
            if not report_oids:
                return []
            query_parts.append({"report_oid": {"$in": report_oids}})
        else:
            sample_scope = []
            if sample_oids:
                sample_scope.append({"sample_oid": {"$in": sample_oids}})
            if sample_names:
                sample_scope.append({"sample_name": {"$in": sample_names}})
            if not sample_scope:
                return []
            query_parts.append({"$or": sample_scope})
        if asp_ids is not None:
            query_parts.append({"assay": {"$in": asp_ids}})
        query: dict[str, Any] = {"$and": query_parts}
        projection = {
            "sample_name": 1,
            "sample_oid": 1,
            "report_id": 1,
            "report_oid": 1,
            "report_num": 1,
            "assay": 1,
            "assay_group": 1,
            "subpanel": 1,
            "analysis_type": 1,
            "finding_type": 1,
            "nomenclature": 1,
            "tier": 1,
            "gene": 1,
            "genes": 1,
            "gene1": 1,
            "gene2": 1,
            "variant": 1,
            "hgvsp": 1,
            "hgvsc": 1,
            "genomic": 1,
            "transcript": 1,
            "simple_id": 1,
            "simple_id_hash": 1,
            "created_on": 1,
            "time_created": 1,
        }
        return list(
            self.get_collection()
            .find(query, projection)
            .sort([("created_on", DESCENDING), ("time_created", DESCENDING)])
            .limit(limit)
        )

    def get_dashboard_tier_stats(self) -> dict:
        """
        Return reported tier distribution for dashboard cards/charts.

        The aggregation reads tiered snapshots from reported_variants and returns:
        {
          "total": {"tier1": int, "tier2": int, "tier3": int, "tier4": int},
          "by_assay": {"ASSAY": {"tier1": int, ...}}
        }
        """
        col = self.get_collection()
        pipeline = [
            {"$match": {"tier": {"$in": [1, 2, 3, 4]}}},
            {
                "$facet": {
                    "totals": [{"$group": {"_id": "$tier", "count": {"$sum": 1}}}],
                    "by_assay": [
                        {
                            "$group": {
                                "_id": {
                                    "assay": {"$ifNull": ["$assay", "Unknown"]},
                                    "tier": "$tier",
                                },
                                "count": {"$sum": 1},
                            }
                        }
                    ],
                }
            },
        ]
        doc = (list(col.aggregate(pipeline, allowDiskUse=True)) or [{}])[0]

        total = {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}
        for row in doc.get("totals", []) or []:
            tier = row.get("_id")
            key = f"tier{tier}"
            if key in total:
                total[key] = int(row.get("count", 0) or 0)

        by_assay: dict[str, dict[str, int]] = {}
        for row in doc.get("by_assay", []) or []:
            key = row.get("_id") or {}
            assay = str(key.get("assay") or "Unknown")
            tier = key.get("tier")
            tier_key = f"tier{tier}"
            if assay not in by_assay:
                by_assay[assay] = {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}
            if tier_key in by_assay[assay]:
                by_assay[assay][tier_key] += int(row.get("count", 0) or 0)

        return {"total": total, "by_assay": by_assay}
