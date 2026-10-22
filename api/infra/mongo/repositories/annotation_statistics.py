"""Annotation classification aggregations for search summaries and dashboards."""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from api.infra.mongo.repositories.annotation_queries import (
    _annotation_search_query,
)


class AnnotationStatisticsMixin:
    """Provide annotation statistics using the owning repository collection."""

    def get_assay_classified_stats(self) -> tuple:
        """
        Retrieve classified statistics for all assays.

        This method constructs an aggregation pipeline to calculate statistics
        for classified variants in the database. It groups the data by assay,
        nomenclature, and classification, and provides counts for each group.

        Returns:
            tuple: A list of dictionaries containing:
                - assay (str): The assay type.
                - nomenclature (str): The nomenclature type ('p', 'c', 'g', etc.).
                - class (int): The classification number.
                - count (int): The count of classified variants for the group.
        """
        assay_class_stats_pipeline = [
            # Match documents where the "class" field exists
            {"$match": {"class": {"$exists": True}}},
            # Sort by variant and time_created to ensure the latest document is first
            {"$sort": {"variant": 1, "time_created": -1}},
            # Group by variant to pick the latest document for each variant
            {
                "$group": {
                    "_id": "$variant",
                    "assay": {"$first": "$assay"},
                    "nomenclature": {"$first": "$nomenclature"},
                    "class": {"$first": "$class"},
                }
            },
            # Group by assay, nomenclature, and class to get counts
            {
                "$group": {
                    "_id": {
                        "assay": "$assay",
                        "nomenclature": "$nomenclature",
                        "class": "$class",
                    },
                    "count": {"$sum": 1},
                }
            },
            # Sort the results by assay, nomenclature, and class for consistency
            {"$sort": {"_id.assay": 1, "_id.nomenclature": 1, "_id.class": 1}},
        ]
        return tuple(self.get_collection().aggregate(assay_class_stats_pipeline))

    def get_classified_stats(self) -> tuple:
        """
        Retrieve statistics for all classified variants.

        This method constructs an aggregation pipeline to calculate statistics
        for classified variants in the database. It groups the data by nomenclature
        and classification, and provides counts for each group.

        Returns:
            list: A list of dictionaries containing:
                - nomenclature (str): The nomenclature type ('p', 'c', 'g', etc.).
                - class (int): The classification number.
                - count (int): The count of classified variants for the group.
        """
        class_stats_pipeline = [
            # Match documents where the "class" field exists
            {"$match": {"class": {"$exists": True}}},
            # Sort by nomenclature, variant, and time_created to ensure the latest document is first
            {"$sort": {"nomenclature": 1, "variant": 1, "time_created": -1}},
            # Group by variant to pick the latest document for each variant
            {
                "$group": {
                    "_id": "$variant",
                    "nomenclature": {"$first": "$nomenclature"},
                    "class": {"$first": "$class"},
                }
            },
            # Group by nomenclature and class to get counts
            {
                "$group": {
                    "_id": {
                        "nomenclature": "$nomenclature",
                        "class": "$class",
                    },
                    "count": {"$sum": 1},
                }
            },
            # Sort the results by nomenclature and class for consistency
            {"$sort": {"_id.nomenclature": 1, "_id.class": 1}},
        ]
        return tuple(self.get_collection().aggregate(class_stats_pipeline))

    def get_tier_stats_by_search(
        self,
        search_str: str,
        search_mode: str,
        include_annotation_text: bool,
        asp_ids: Optional[List[str]] = None,
        nomenclatures: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Return tier stats for the given search filter.

        Output shape:
        {
        "total":   {"tier1": int, "tier2": int, "tier3": int, "tier4": int},
        "by_assay": {
            "<assay>": {"tier1": int, "tier2": int, "tier3": int, "tier4": int},
            ...
        }
        }

        Rules:
        - Only docs with `class` are counted.
        - "Latest" is selected by `time_created` (descending).
        - Assay stats: dedupe per (assay + variant_key).
        - Total stats: dedupe per (variant_key) across assays (so no double counting).
        """

        if not search_str:
            return {"total": {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}, "by_assay": {}}

        query = _annotation_search_query(
            search_str=search_str,
            search_mode=search_mode,
            include_annotation_text=include_annotation_text,
            asp_ids=asp_ids,
            nomenclatures=nomenclatures,
        )
        if query is None:
            return {"total": {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}, "by_assay": {}}

        query["class"] = {"$exists": True, "$ne": None}

        # --- dedupe keys ---
        # total: dedupe across assays (avoid counting same variant multiple times)
        total_variant_key = {
            "nomenclature": "$nomenclature",
            "variant": "$variant",
            "gene": "$gene",
            "gene1": "$gene1",
            "gene2": "$gene2",
            "transcript": "$transcript",
        }

        # by_assay: dedupe within assay (same variant can be re-tiered in same assay)
        per_assay_variant_key = {
            "assay": "$assay",
            "nomenclature": "$nomenclature",
            "variant": "$variant",
            "gene": "$gene",
            "gene1": "$gene1",
            "gene2": "$gene2",
            "transcript": "$transcript",
        }

        def _tier_rollup_stage():
            """Tier rollup stage.

            Returns:
                    The  tier rollup stage result.
            """
            return [
                {
                    "$group": {
                        "_id": None,
                        "tier1": {"$sum": {"$cond": [{"$eq": ["$_id.class", 1]}, "$count", 0]}},
                        "tier2": {"$sum": {"$cond": [{"$eq": ["$_id.class", 2]}, "$count", 0]}},
                        "tier3": {"$sum": {"$cond": [{"$eq": ["$_id.class", 3]}, "$count", 0]}},
                        "tier4": {"$sum": {"$cond": [{"$eq": ["$_id.class", 4]}, "$count", 0]}},
                    }
                },
                {"$project": {"_id": 0, "tier1": 1, "tier2": 1, "tier3": 1, "tier4": 1}},
            ]

        col = self.get_collection()

        # -------------------------
        # (1) TOTAL stats (no double counting across assays)
        # -------------------------
        total_pipeline = [
            {"$match": query},
            {"$sort": {"variant": 1, "gene": 1, "time_created": -1}},
            {"$group": {"_id": total_variant_key, "class": {"$first": "$class"}}},
            {"$group": {"_id": {"class": "$class"}, "count": {"$sum": 1}}},
            *_tier_rollup_stage(),
        ]
        total_res = list(col.aggregate(total_pipeline))
        total_stats = (
            total_res[0] if total_res else {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}
        )

        # -------------------------
        # (2) ASSAY-specific stats
        # -------------------------
        by_assay_pipeline = [
            {"$match": query},
            {"$sort": {"assay": 1, "variant": 1, "gene": 1, "time_created": -1}},
            {"$group": {"_id": per_assay_variant_key, "class": {"$first": "$class"}}},
            {"$group": {"_id": {"assay": "$_id.assay", "class": "$class"}, "count": {"$sum": 1}}},
            # fold per assay into a single doc per assay
            {
                "$group": {
                    "_id": "$_id.assay",
                    "tier1": {"$sum": {"$cond": [{"$eq": ["$_id.class", 1]}, "$count", 0]}},
                    "tier2": {"$sum": {"$cond": [{"$eq": ["$_id.class", 2]}, "$count", 0]}},
                    "tier3": {"$sum": {"$cond": [{"$eq": ["$_id.class", 3]}, "$count", 0]}},
                    "tier4": {"$sum": {"$cond": [{"$eq": ["$_id.class", 4]}, "$count", 0]}},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "assay": "$_id",
                    "tier1": 1,
                    "tier2": 1,
                    "tier3": 1,
                    "tier4": 1,
                }
            },
            {"$sort": {"assay": 1}},
        ]
        by_assay_docs = list(col.aggregate(by_assay_pipeline))
        by_assay = defaultdict(
            lambda: {
                "tier1": 0,
                "tier2": 0,
                "tier3": 0,
                "tier4": 0,
            }
        )

        for d in by_assay_docs:
            if not d:
                assay = "Historic"
                tiers = {}
            else:
                assay = d.get("assay") or "Historic"
                tiers = d

            by_assay[assay]["tier1"] += tiers.get("tier1", 0) or 0
            by_assay[assay]["tier2"] += tiers.get("tier2", 0) or 0
            by_assay[assay]["tier3"] += tiers.get("tier3", 0) or 0
            by_assay[assay]["tier4"] += tiers.get("tier4", 0) or 0

        # Optional: convert back to normal dict
        by_assay = dict(by_assay)

        return {"total": total_stats, "by_assay": by_assay}

    def get_dashboard_classification_stats(self) -> dict[str, Any]:
        """Return latest current classifications for dashboard inventory.

        A finding is counted once globally and once per assay. Reclassifications
        replace earlier values by selecting the newest annotation for the same
        canonical annotation identity.
        """
        match = {"class": {"$in": [1, 2, 3, 4]}}
        identity = {
            "nomenclature": "$nomenclature",
            "variant": "$variant",
            "gene": "$gene",
            "gene1": "$gene1",
            "gene2": "$gene2",
            "transcript": "$transcript",
        }

        def tier_fields() -> dict[str, Any]:
            """Build aggregation accumulators counting each class from one through four.

            Returns:
                Tier-named ``$sum`` expressions contributing one for a matching class.
            """
            return {
                f"tier{tier}": {"$sum": {"$cond": [{"$eq": ["$class", tier]}, 1, 0]}}
                for tier in range(1, 5)
            }

        total_pipeline = [
            {"$match": match},
            {"$sort": {"time_created": -1, "_id": -1}},
            {"$group": {"_id": identity, "class": {"$first": "$class"}}},
            {"$group": {"_id": None, **tier_fields()}},
            {"$project": {"_id": 0, "tier1": 1, "tier2": 1, "tier3": 1, "tier4": 1}},
        ]
        total_rows = list(self.get_collection().aggregate(total_pipeline, allowDiskUse=True))
        total = total_rows[0] if total_rows else {f"tier{tier}": 0 for tier in range(1, 5)}

        by_assay_pipeline = [
            {"$match": match},
            {"$sort": {"time_created": -1, "_id": -1}},
            {"$group": {"_id": {"assay": "$assay", **identity}, "class": {"$first": "$class"}}},
            {"$group": {"_id": "$_id.assay", **tier_fields()}},
            {
                "$project": {
                    "_id": 0,
                    "assay": {"$ifNull": ["$_id", "Historic"]},
                    "tier1": 1,
                    "tier2": 1,
                    "tier3": 1,
                    "tier4": 1,
                }
            },
            {"$sort": {"assay": 1}},
        ]
        by_assay = {
            str(row.pop("assay")): row
            for row in self.get_collection().aggregate(by_assay_pipeline, allowDiskUse=True)
        }
        return {"total": total, "by_assay": by_assay}

    def get_dashboard_top_tiered_genes(self, *, limit: int = 15) -> list[dict[str, Any]]:
        """Rank genes by unique biological findings and their latest classifications."""
        bounded_limit = max(1, min(int(limit), 20))
        tier_fields = {
            f"tier{tier}": {"$sum": {"$cond": [{"$eq": ["$class", tier]}, 1, 0]}}
            for tier in range(1, 5)
        }

        def gene_facet(field: str, *, exclude_matching_gene1: bool = False) -> list[dict[str, Any]]:
            """Build stages counting tiered findings for one nonempty gene field.

            Args:
                field: Gene field to filter and group by.
                exclude_matching_gene1: Exclude rows equal to gene1 to avoid counting
                    the same partner twice; defaults to false.

            Returns:
                Match and group stages collecting totals, tier counts, and nomenclature sets.
            """
            match: dict[str, Any] = {field: {"$nin": [None, ""]}}
            if exclude_matching_gene1:
                match["$expr"] = {"$ne": [f"${field}", "$gene1"]}
            return [
                {"$match": match},
                {
                    "$group": {
                        "_id": f"${field}",
                        "total": {"$sum": 1},
                        **tier_fields,
                        "nomenclature_sets": {"$push": "$nomenclatures"},
                    }
                },
            ]

        pipeline = [
            {"$match": {"class": {"$in": [1, 2, 3, 4]}}},
            {
                "$set": {
                    "biological_type": {
                        "$cond": [
                            {"$in": ["$nomenclature", ["p", "c", "g"]]},
                            "small_variant",
                            "$nomenclature",
                        ]
                    },
                    "biological_identity": {
                        "$cond": [
                            {"$in": ["$nomenclature", ["p", "c", "g"]]},
                            {
                                "$ifNull": [
                                    "$genomic_hash",
                                    {"$ifNull": ["$genomic", "$variant"]},
                                ]
                            },
                            "$variant",
                        ]
                    },
                }
            },
            {"$sort": {"time_created": -1, "_id": -1}},
            {
                "$group": {
                    "_id": {
                        "type": "$biological_type",
                        "identity": "$biological_identity",
                        "gene": "$gene",
                        "gene1": "$gene1",
                        "gene2": "$gene2",
                    },
                    "class": {"$first": "$class"},
                    "gene": {"$first": "$gene"},
                    "gene1": {"$first": "$gene1"},
                    "gene2": {"$first": "$gene2"},
                    "nomenclatures": {"$addToSet": "$nomenclature"},
                }
            },
            {
                "$facet": {
                    "gene": gene_facet("gene"),
                    "gene1": gene_facet("gene1"),
                    "gene2": gene_facet("gene2", exclude_matching_gene1=True),
                }
            },
        ]
        aggregate_rows = list(self.get_collection().aggregate(pipeline, allowDiskUse=True))
        grouped: dict[str, dict[str, Any]] = {}
        for facet_rows in aggregate_rows[0].values() if aggregate_rows else []:
            for row in facet_rows:
                gene = str(row.get("_id") or "").strip().upper()
                if not gene:
                    continue
                target = grouped.setdefault(
                    gene,
                    {
                        "gene": gene,
                        "total": 0,
                        "tier1": 0,
                        "tier2": 0,
                        "tier3": 0,
                        "tier4": 0,
                        "nomenclatures": set(),
                    },
                )
                target["total"] += int(row.get("total") or 0)
                for tier in range(1, 5):
                    target[f"tier{tier}"] += int(row.get(f"tier{tier}") or 0)
                for values in row.get("nomenclature_sets", []):
                    target["nomenclatures"].update(value for value in values if value)

        rows = sorted(grouped.values(), key=lambda row: (-row["total"], row["gene"]))
        for row in rows:
            row["nomenclatures"] = sorted(row["nomenclatures"])
        return rows[:bounded_limit]
