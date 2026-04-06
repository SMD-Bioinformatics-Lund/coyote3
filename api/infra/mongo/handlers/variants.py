"""
VariantsHandler module for Coyote3
==================================

This module defines the `VariantsHandler` class used for accessing and managing
variant data in MongoDB.
It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from datetime import datetime, timezone
from typing import Any

from bson.objectid import ObjectId

from api.core.dna.variant_identity import (
    build_simple_id_hash_from_simple_id,
    ensure_variant_identity_fields,
    normalize_simple_id,
)
from api.infra.dashboard_cache import invalidate_dashboard_summary_cache
from api.infra.mongo.handlers.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class VariantsHandler(BaseHandler):
    """
    VariantsHandler is a class for managing variant data in the database.

    This class provides methods to perform CRUD operations, manage comments,
    and handle specific flags (e.g., `interesting`, `false positive`, `irrelevant`) for variants.
    It also includes utility methods for retrieving annotations, counting unique variants,
    and deleting variants associated with a sample.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.variants_collection)

    def ensure_indexes(self) -> None:
        """
        Create required indexes for variant-heavy read paths.

        Safe to call multiple times; MongoDB keeps existing indexes.
        """
        col = self.get_collection()
        col.create_index(
            [("simple_id_hash", 1), ("simple_id", 1)],
            name="simple_id_hash_1_simple_id_1",
            background=True,
            partialFilterExpression={
                "simple_id_hash": {"$exists": True, "$type": "string"},
                "simple_id": {"$exists": True, "$type": "string"},
            },
        )
        # Non-partial lookup index for Mongo planner reliability on equality predicates.
        col.create_index(
            [("simple_id_hash", 1), ("simple_id", 1)],
            name="ix_simple_id_hash_simple_id_lookup",
            background=True,
        )
        col.create_index(
            [("simple_id_hash", 1), ("simple_id", 1), ("SAMPLE_ID", 1)],
            name="simple_id_hash_1_simple_id_1_sample_id_1",
            background=True,
            partialFilterExpression={
                "simple_id_hash": {"$exists": True, "$type": "string"},
                "simple_id": {"$exists": True, "$type": "string"},
                "SAMPLE_ID": {"$exists": True, "$type": "string"},
            },
        )
        col.create_index(
            [("simple_id_hash", 1), ("simple_id", 1), ("SAMPLE_ID", 1)],
            name="ix_simple_id_hash_simple_id_sample_lookup",
            background=True,
        )
        col.create_index(
            [("SAMPLE_ID", 1)],
            name="sample_id_1",
            background=True,
        )
        col.create_index(
            [("variant_class", 1)],
            name="variant_class_1",
            background=True,
        )
        col.create_index(
            [("fp", 1)],
            name="fp_1",
            background=True,
        )
        col.create_index(
            [("fp", 1), ("simple_id_hash", 1), ("simple_id", 1)],
            name="fp_1_simple_id_hash_1_simple_id_1",
            background=True,
            partialFilterExpression={
                "simple_id_hash": {"$exists": True, "$type": "string"},
                "simple_id": {"$exists": True, "$type": "string"},
            },
        )

    def get_case_variants(self, query: dict):
        """
        Retrieve variants based on a constructed query.

        This method executes a query on the variants collection and returns the matching variants.

        Args:
            query (dict): A dictionary representing the query to execute.

        Returns:
            pymongo.cursor.Cursor: A cursor to the documents that match the query.
        """
        return self.get_collection().find(query)

    @staticmethod
    def _simple_id_identity_query(simple_id: str) -> dict[str, str]:
        """Build exact identity query using hash prefilter + simple_id verification."""
        normalized = normalize_simple_id(simple_id)
        return {
            "simple_id_hash": build_simple_id_hash_from_simple_id(normalized),
            "simple_id": normalized,
        }

    def _dashboard_metrics_collection(self):
        """Return persistent metrics collection used for cold-start fast reads."""
        return self.adapter.coyote_db["dashboard_metrics"]

    def invalidate_dashboard_metrics_cache(self) -> None:
        """Invalidate variant dashboard counters in redis + persisted metrics."""
        cache = getattr(self.adapter.app, "cache", None)
        if cache is not None:
            cache.set("dashboard:variant_rollup:v1", None, timeout=1)
            cache.set("dashboard:variant_unique_quality:v1", None, timeout=1)
        self._dashboard_metrics_collection().delete_many(
            {"_id": {"$in": ["variant_rollup_v1", "variant_unique_quality_v1"]}}
        )
        invalidate_dashboard_summary_cache(self.adapter)

    def _read_persisted_metric(
        self, metric_key: str, max_age_seconds: int | None = None
    ) -> dict | None:
        """Read a persisted dashboard metric payload if present and fresh enough."""
        doc = self._dashboard_metrics_collection().find_one(
            {"_id": metric_key}, {"payload": 1, "updated_at": 1}
        )
        if not isinstance(doc, dict):
            return None
        payload = doc.get("payload")
        if not isinstance(payload, dict):
            return None
        if max_age_seconds is None:
            return payload
        updated_at = doc.get("updated_at")
        if not isinstance(updated_at, datetime):
            return None
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - updated_at).total_seconds()
        if age_seconds > max_age_seconds:
            return None
        return payload

    def _write_persisted_metric(self, metric_key: str, payload: dict[str, Any]) -> None:
        """Upsert a persisted dashboard metric payload."""
        self._dashboard_metrics_collection().update_one(
            {"_id": metric_key},
            {"$set": {"payload": dict(payload), "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    def get_variant(self, id: str) -> dict:
        """
        Retrieve a variant by its unique ID.

        This method fetches a single variant document from the database
        using its unique ObjectId.

        Args:
            id (str): The unique identifier of the variant.

        Returns:
            dict: A dictionary representing the variant document, or None if not found.
        """
        return self.get_collection().find_one({"_id": ObjectId(id)})

    def get_variant_in_other_samples(self, variant: dict) -> list:
        """
        Retrieve the same variant from other samples using a fast 2-query method.

        This method identifies variants with the same `simple_id` but from different samples
        and includes additional information such as `sample_name`, `groups`, and `GT`
        (Genotype) for each variant.

        Returns:
            list: A list of dictionaries, each containing details about the variant
                and its associated sample, including `sample_name`, `groups`, `GT`,
                and flags like `fp`, `interesting`, and `irrelevant`.
        """
        canonical_variant = ensure_variant_identity_fields(variant)
        current_sample_id = canonical_variant["SAMPLE_ID"]
        simple_id = canonical_variant["simple_id"]
        simple_id_hash = canonical_variant["simple_id_hash"]

        # Hash-first identity prefilter. Filter current sample in-memory to avoid
        # poor plans on SAMPLE_ID != value (which can trigger near full-index scans).
        variants_cursor = (
            self.get_collection()
            .find(
                {
                    "simple_id_hash": simple_id_hash,
                    "simple_id": simple_id,
                },
                {
                    "_id": 1,
                    "SAMPLE_ID": 1,
                    "simple_id_hash": 1,
                    "simple_id": 1,
                    "GT": 1,
                    "fp": 1,
                    "interesting": 1,
                    "irrelevant": 1,
                },
            )
            .limit(100)
        )
        variants = [
            row
            for row in variants_cursor
            if str(row.get("SAMPLE_ID", "")) != str(current_sample_id)
        ][:20]

        # Collect only the sample ObjectIds we need
        sample_ids = {ObjectId(v["SAMPLE_ID"]) for v in variants}

        # Step 3: Map sample_id -> {name, assay}
        sample_map = {
            str(s["_id"]): {
                "sample_name": s.get("name", "unknown"),
                "assay": s.get("assay", "unknown"),
            }
            for s in self.adapter.samples_collection.find(
                {"_id": {"$in": list(sample_ids)}},
                {"_id": 1, "name": 1, "assay": 1},
            )
        }

        # Attach GT to each sample_info
        results = []
        for v in variants:
            sid = v["SAMPLE_ID"]
            info = sample_map.get(sid, {"sample_name": "unknown", "assay": "unknown"})
            info["GT"] = v.get("GT")
            info["fp"] = v.get("fp", False)  # Add fp status if available
            info["interesting"] = v.get("interesting", False)  # Add interesting status if available
            info["irrelevant"] = v.get("irrelevant", False)  # Add irrelevant status if available
            results.append(info)

        return results

    def get_variants_by_identity(
        self, *, simple_id: str, sample_id: str | None = None, limit: int | None = None
    ) -> list[dict]:
        """
        Find variants by exact identity using hash prefilter + simple_id verification.
        """
        query: dict[str, Any] = self._simple_id_identity_query(simple_id)
        if sample_id is not None:
            query["SAMPLE_ID"] = sample_id
        cursor = self.get_collection().find(query)
        if limit is not None:
            cursor = cursor.limit(limit)
        return list(cursor)

    def get_variants_by_gene(self, gene: str) -> Any:
        """
        Retrieve variants associated with a specific gene.

        This method queries the database to find all variants that are linked
        to the specified gene.

        Args:
            gene (str): The name of the gene to search for.

        Returns:
            Any: A cursor to the documents that match the query or None if not found.
        """
        return self.get_collection().find({"genes": gene})

    def get_variants_by_gene_plus_variant_list(self, gene: str, variant_list: list) -> Any:
        """
        Retrieve variants for a gene filtered by a list of variant identifiers.

        Matches documents where `genes` contains `gene` and any of the values in
        `variant_list` appear in `HGVSp`, `HGVSc`, or `simple_id`.

        Args:
            gene (str): Gene name to search.
            variant_list (list[str]): List of variant identifiers (HGVSp, HGVSc or simple_id).

        Returns:
            pymongo.cursor.Cursor: Cursor over matching variant documents.
        """
        identity_conditions: list[dict] = []
        for value in variant_list:
            raw = str(value or "").strip()
            if not raw:
                continue
            # simple_id format is CHROM_POS_REF_ALT (ALT may contain underscores).
            if len(raw.split("_", 3)) == 4:
                identity_conditions.append(self._simple_id_identity_query(raw))

        query_or: list[dict] = [
            {"HGVSp": {"$in": variant_list}},
            {"HGVSc": {"$in": variant_list}},
        ]
        query_or.extend(identity_conditions)

        return self.get_collection().find(
            {
                "genes": gene,
                "$or": query_or,
            },
            {
                "_id": 1,
                "CHROM": 1,
                "POS": 1,
                "REF": 1,
                "ALT": 1,
                "SAMPLE_ID": 1,
                "simple_id": 1,
                "HGVSp": 1,
                "HGVSc": 1,
                "genes": 1,
                "fp": 1,
                "interesting": 1,
                "irrelevant": 1,
                "selected_csq_feature": 1,
                "variant_class": 1,
                "gnomad_frequency": 1,
                "gnomad_max": 1,
                "exac_frequency": 1,
                "thousandG_frequency": 1,
                "QUAL": 1,
                "FILTER": 1,
                "GT": 1,
                "INFO.variant_callers": 1,
                "INFO.selected_CSQ": 1,
                "INFO.selected_CSQ_criteria": 1,
            },
        )

    def mark_false_positive_var(self, variant_id: str, fp: bool = True) -> Any:
        """
        Mark the false positive status of a variant.

        This method updates the `fp` (false positive) flag for a specific variant
        in the database.

        Args:
            variant_id (str): The unique identifier of the variant to update.
            fp (bool, optional): The false positive status to set. Defaults to True.

        Returns:
            Any: The result of the update operation.
        """
        result = self.get_collection().update_one(
            {"_id": ObjectId(variant_id)},
            {"$set": {"fp": fp}},
        )
        if result.matched_count:
            self.invalidate_dashboard_metrics_cache()
        return result

    def unmark_false_positive_var(self, variant_id: str, fp: bool = False) -> Any:
        """
        Unmark the false positive status of a variant.

        This method updates the `fp` (false positive) flag for a specific variant
        in the database to indicate it is no longer marked as a false positive.

        Args:
            variant_id (str): The unique identifier of the variant to update.
            fp (bool, optional): The false positive status to set. Defaults to False.

        Returns:
            Any: The result of the update operation.
        """
        return self.mark_false_positive_var(variant_id, fp)

    def mark_false_positive_var_bulk(self, variant_ids: list[str], fp: bool = True) -> Any:
        """
        Mark multiple variants as false positive.

        Args:
            variant_ids (list[str]): List of variant document IDs.
            fp (bool, optional): The false positive status to set. Defaults to True.

        Returns:
            Any: The result of the bulk update operation.
        """
        result = self.mark_false_positive_bulk(variant_ids, fp)
        if result is not None and getattr(result, "matched_count", 0):
            self.invalidate_dashboard_metrics_cache()
        return result

    def unmark_false_positive_var_bulk(self, variant_ids: list[str], fp: bool = False) -> Any:
        """
        Unmark multiple variants as false positive.

        Args:
            variant_ids (list[str]): List of variant document IDs.
            fp (bool, optional): The false positive status to set. Defaults to False.

        Returns:
            Any: The result of the bulk update operation.
        """
        return self.mark_false_positive_var_bulk(variant_ids, fp)

    def mark_interesting_var(self, variant_id: str, interesting: bool = True) -> Any:
        """
        Mark the variant as interesting.

        This method updates the `interesting` flag for a specific variant
        in the database to indicate it is noteworthy.

        Args:
            variant_id (str): The unique identifier of the variant to update.
            interesting (bool, optional): The interesting status to set. Defaults to True.

        Returns:
            Any: The result of the update operation.
        """
        self.mark_interesting(variant_id, interesting)

    def unmark_interesting_var(self, variant_id: str, interesting: bool = False) -> Any:
        """
        Unmark the variant as not interesting.

        This method updates the `interesting` flag for a specific variant
        in the database to indicate it is no longer considered interesting.

        Args:
            variant_id (str): The unique identifier of the variant to update.
            interesting (bool, optional): The interesting status to set. Defaults to False.

        Returns:
            Any: The result of the update operation.
        """
        self.mark_interesting(variant_id, interesting)

    def mark_irrelevant_var(self, variant_id: str, irrelevant: bool = True) -> Any:
        """
        Mark the variant as irrelevant.

        This method updates the `irrelevant` flag for a specific variant
        in the database to indicate it is not relevant.

        Args:
            variant_id (str): The unique identifier of the variant to update.
            irrelevant (bool, optional): The irrelevant status to set. Defaults to True.

        Returns:
            Any: The result of the update operation.
        """
        self.mark_irrelevant(variant_id, irrelevant)

    def unmark_irrelevant_var(self, variant_id: str, irrelevant: bool = False) -> Any:
        """
        Unmark the variant as relevant.

        This method updates the `irrelevant` flag for a specific variant
        in the database to indicate it is now considered relevant.

        Args:
            variant_id (str): The unique identifier of the variant to update.
            irrelevant (bool, optional): The irrelevant status to set. Defaults to False.

        Returns:
            Any: The result of the update operation.
        """
        self.mark_irrelevant(variant_id, irrelevant)

    def mark_irrelevant_var_bulk(self, variant_ids: list[str], irrelevant: bool = True) -> Any:
        """
        Mark multiple variants as irrelevant.

        Args:
            variant_ids (list[str]): List of variant document IDs.
            irrelevant (bool, optional): The status to set. Defaults to True.
        """
        return self.mark_irrelevant_bulk(variant_ids, irrelevant)

    def unmark_irrelevant_var_bulk(self, variant_ids: list[str], irrelevant: bool = False) -> Any:
        """
        Unmark multiple variants as irrelevant.

        Args:
            variant_ids (list[str]): List of variant document IDs.
            irrelevant (bool, optional): The status to set. Defaults to False.
        """
        return self.mark_irrelevant_bulk(variant_ids, irrelevant)

    def hide_var_comment(self, id: str, comment_id: str) -> Any:
        """
        Hide a comment associated with a specific variant.

        This method hides a comment for a given variant by its ID and the comment's ID.

        Args:
            id (str): The unique identifier of the variant.
            comment_id (str): The unique identifier of the comment to hide.

        Returns:
            Any: The result of the hide operation.
        """
        self.hide_comment(id, comment_id)

    def unhide_variant_comment(self, id: str, comment_id: str) -> Any:
        """
        Unhide a comment associated with a specific variant.

        This method unhides a comment for a given variant by its ID and the comment's ID.

        Args:
            id (str): The unique identifier of the variant.
            comment_id (str): The unique identifier of the comment to unhide.

        Returns:
            Any: The result of the unhide operation.
        """
        self.unhide_comment(id, comment_id)

    def add_var_comment(self, id: str, comment: dict) -> Any:
        """
        Add a comment to a specific variant.

        This method updates the database to include a new comment for a given variant.

        Args:
            id (str): The unique identifier of the variant.
            comment (dict): A dictionary containing the comment details.

        Returns:
            Any: The result of the update operation.
        """
        self.update_comment(id, comment)

    def hidden_var_comments(self, id: str) -> bool:
        """
        Check if there are hidden comments for a specific variant.

        This method determines whether a variant has any hidden comments.

        Args:
            id (str): The unique identifier of the variant.

        Returns:
            bool: True if there are hidden comments, False otherwise.
        """
        return self.hidden_comments(id)

    def get_total_variant_counts(self) -> int:
        """
        Get the total count of variants in the collection.

        This method queries the database to count all the variant documents
        present in the variants collection.

        Returns:
            int: The total number of variants in the collection.
        """
        return self.get_collection().count_documents({})

    def get_unique_total_variant_counts(self) -> int:
        """
        Get the count of all unique variants in the collection.

        This method uses MongoDB aggregation to group variants by their unique
        chromosome (CHROM), position (POS), reference allele (REF), and alternate allele (ALT).
        It then counts the total number of unique groups.

        Returns:
            int: The total count of unique variants in the collection.
        """
        result = list(
            self.get_collection().aggregate(
                [
                    {
                        "$match": {
                            "simple_id_hash": {"$exists": True, "$type": "string"},
                            "simple_id": {"$exists": True, "$type": "string"},
                        }
                    },
                    {"$group": {"_id": {"hash": "$simple_id_hash", "simple_id": "$simple_id"}}},
                    {"$count": "count"},
                ],
                allowDiskUse=True,
            )
        )
        if not result:
            return 0
        return int(result[0].get("count", 0) or 0)

    def get_unique_variant_quality_counts(self) -> dict[str, int]:
        """
        Return unique identity counts for dashboard quality metrics.

        Uses one pass to compute:
          - unique_total_variants
          - unique_fp_variants (identity had at least one document with fp=True)
        """
        app_obj = self.adapter.app
        cache = getattr(app_obj, "cache", None)
        cache_key = "dashboard:variant_unique_quality:v1"
        if cache is not None:
            cached = cache.get(cache_key)
            if isinstance(cached, dict):
                return {
                    "unique_total_variants": int(cached.get("unique_total_variants", 0) or 0),
                    "unique_fp_variants": int(cached.get("unique_fp_variants", 0) or 0),
                }
        persisted_metric = self._read_persisted_metric(
            "variant_unique_quality_v1",
            max_age_seconds=int(
                app_obj.config.get("DASHBOARD_UNIQUE_VARIANT_METRIC_MAX_AGE", 86400)
            ),
        )
        if isinstance(persisted_metric, dict):
            current_estimated_total = int(self.get_collection().estimated_document_count() or 0)
            metric_estimated_total = int(
                persisted_metric.get(
                    "source_total_variants", persisted_metric.get("unique_total_variants", 0)
                )
                or 0
            )
            if current_estimated_total != metric_estimated_total:
                persisted_metric = None
        if isinstance(persisted_metric, dict):
            payload = {
                "unique_total_variants": int(persisted_metric.get("unique_total_variants", 0) or 0),
                "unique_fp_variants": int(persisted_metric.get("unique_fp_variants", 0) or 0),
            }
            if cache is not None:
                timeout = int(app_obj.config.get("DASHBOARD_UNIQUE_VARIANT_CACHE_TTL", 1800))
                cache.set(cache_key, payload, timeout=timeout)
            return payload

        pipeline = [
            {
                "$match": {
                    "simple_id_hash": {"$exists": True, "$type": "string"},
                    "simple_id": {"$exists": True, "$type": "string"},
                }
            },
            {
                "$group": {
                    "_id": {"hash": "$simple_id_hash", "simple_id": "$simple_id"},
                    "fp_any": {"$max": {"$cond": [{"$eq": ["$fp", True]}, 1, 0]}},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "unique_total_variants": {"$sum": 1},
                    "unique_fp_variants": {"$sum": "$fp_any"},
                }
            },
            {"$project": {"_id": 0, "unique_total_variants": 1, "unique_fp_variants": 1}},
        ]
        row = (list(self.get_collection().aggregate(pipeline, allowDiskUse=True)) or [{}])[0]
        payload = {
            "unique_total_variants": int(row.get("unique_total_variants", 0) or 0),
            "unique_fp_variants": int(row.get("unique_fp_variants", 0) or 0),
            "source_total_variants": int(self.get_collection().estimated_document_count() or 0),
        }
        self._write_persisted_metric("variant_unique_quality_v1", payload)
        if cache is not None:
            timeout = int(app_obj.config.get("DASHBOARD_UNIQUE_VARIANT_CACHE_TTL", 1800))
            cache.set(cache_key, payload, timeout=timeout)
        return payload

    def get_total_snp_counts(self) -> int:
        """
        Get the total count of SNP (Single Nucleotide Polymorphism) variants.

        This method retrieves all variant documents where the `variant_class` is "SNV"
        (Single Nucleotide Variant), which typically represents SNPs, and returns their count.

        Returns:
            int: The total number of SNP variants in the collection.
        """
        return self.get_collection().count_documents({"variant_class": "SNV"})

    def get_fp_counts(self):
        """
        Get the total count of false positive variants.

        This method retrieves all variant documents marked as false positive
        in the collection and returns their count.

        Returns:
            int: The total number of false positive variants in the collection.
        """
        return self.get_collection().count_documents({"fp": True})

    def get_dashboard_variant_counts(self) -> dict[str, int]:
        """
        Return variant summary counters for dashboard.

        Output keys:
          - total_variants
          - total_snps
          - fps
        """
        app_obj = self.adapter.app
        cache = getattr(app_obj, "cache", None)
        cache_key = "dashboard:variant_rollup:v1"
        if cache is not None:
            cached = cache.get(cache_key)
            if isinstance(cached, dict):
                return {
                    "total_variants": int(cached.get("total_variants", 0) or 0),
                    "total_snps": int(cached.get("total_snps", 0) or 0),
                    "fps": int(cached.get("fps", 0) or 0),
                }

        persisted_metric = self._read_persisted_metric(
            "variant_rollup_v1",
            max_age_seconds=int(
                app_obj.config.get("DASHBOARD_VARIANT_ROLLUP_METRIC_MAX_AGE", 86400)
            ),
        )
        if isinstance(persisted_metric, dict):
            current_estimated_total = int(self.get_collection().estimated_document_count() or 0)
            persisted_total = int(persisted_metric.get("total_variants", 0) or 0)
            if current_estimated_total != persisted_total:
                persisted_metric = None
        if isinstance(persisted_metric, dict):
            payload = {
                "total_variants": int(persisted_metric.get("total_variants", 0) or 0),
                "total_snps": int(persisted_metric.get("total_snps", 0) or 0),
                "fps": int(persisted_metric.get("fps", 0) or 0),
            }
            if cache is not None:
                timeout = int(app_obj.config.get("DASHBOARD_VARIANT_ROLLUP_CACHE_TTL", 1800))
                cache.set(cache_key, payload, timeout=timeout)
            return payload

        col = self.get_collection()
        payload = {
            "total_variants": int(col.estimated_document_count() or 0),
            "total_snps": int(col.count_documents({"variant_class": "SNV"}) or 0),
            "fps": int(col.count_documents({"fp": True}) or 0),
        }
        self._write_persisted_metric("variant_rollup_v1", payload)
        if cache is not None:
            timeout = int(app_obj.config.get("DASHBOARD_VARIANT_ROLLUP_CACHE_TTL", 1800))
            cache.set(cache_key, payload, timeout=timeout)
        return payload

    def get_unique_snp_count(self) -> int:
        """
        Get the count of unique SNP (Single Nucleotide Polymorphism) variants.

        This method retrieves all unique variant `simple_id`s where the `variant_class` is "SNV"
        (Single Nucleotide Variant), which typically represents SNPs, and returns their count.

        Returns:
            int: The number of unique SNP variants in the collection.
        """
        result = list(
            self.get_collection().aggregate(
                [
                    {
                        "$match": {
                            "variant_class": "SNV",
                            "simple_id_hash": {"$exists": True, "$type": "string"},
                            "simple_id": {"$exists": True, "$type": "string"},
                        }
                    },
                    {"$group": {"_id": {"hash": "$simple_id_hash", "simple_id": "$simple_id"}}},
                    {"$count": "count"},
                ],
                allowDiskUse=True,
            )
        )
        if not result:
            return 0
        return int(result[0].get("count", 0) or 0)

    def get_unique_fp_count(self) -> int:
        """
        Get the count of unique false positive variants.

        Returns:
            int: The number of unique variants marked as false positive in the collection.
        """
        result = list(
            self.get_collection().aggregate(
                [
                    {
                        "$match": {
                            "fp": True,
                            "simple_id_hash": {"$exists": True, "$type": "string"},
                            "simple_id": {"$exists": True, "$type": "string"},
                        }
                    },
                    {"$group": {"_id": {"hash": "$simple_id_hash", "simple_id": "$simple_id"}}},
                    {"$count": "count"},
                ],
                allowDiskUse=True,
            )
        )
        if not result:
            return 0
        return int(result[0].get("count", 0) or 0)

    def delete_sample_variants(self, sample_oid: str) -> Any:
        """
        Delete all variants from the variants collection for a given sample OID.

        This method removes all variant documents associated with a specific sample
        from the database.

        Args:
            sample_oid (str): The unique identifier (ObjectId) of the sample whose variants are to be deleted.

        Returns:
            Any: The result of the delete operation, typically a DeleteResult object containing details about the operation.
        """
        result = self.get_collection().delete_many({"SAMPLE_ID": sample_oid})
        if getattr(result, "deleted_count", 0):
            self.invalidate_dashboard_metrics_cache()
        return result

    def get_variant_stats(self, sample_id: str, genes: list | None = None) -> dict:
        """
        Retrieve variant statistics for a specific sample.

        This method aggregates various statistics about the variants associated
        with a given sample, including total counts, counts of false positives,
        interesting variants, irrelevant variants, and counts by variant class.

        Args:
            sample_id (str): The unique identifier of the sample to retrieve statistics for.
            genes (list | None, optional): A list of gene names to filter the variants by.
                If provided, only variants associated with these genes will be considered.
                Defaults to None.
        Returns:
            dict: A dictionary containing various statistics about the variants for the specified sample.
        """

        query = {"SAMPLE_ID": sample_id}
        if genes:
            query["genes"] = {"$in": genes}

        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": "$variant_class",
                    "count": {"$sum": 1},
                    "fp_count": {"$sum": {"$cond": [{"$eq": ["$fp", True]}, 1, 0]}},
                    "interesting_count": {
                        "$sum": {"$cond": [{"$eq": ["$interesting", True]}, 1, 0]}
                    },
                    "irrelevant_count": {"$sum": {"$cond": [{"$eq": ["$irrelevant", True]}, 1, 0]}},
                }
            },
        ]

        results = list(self.get_collection().aggregate(pipeline))

        stats = {
            "variants": 0,
            "false_positives": 0,
            "interesting": 0,
            "irrelevant": 0,
            "by_variant_class": {},
        }

        for result in results:
            variant_class = result["_id"] or "Unknown"
            count = result["count"]
            fp_count = result["fp_count"]
            interesting_count = result["interesting_count"]
            irrelevant_count = result["irrelevant_count"]

            stats["variants"] += count
            stats["false_positives"] += fp_count
            stats["interesting"] += interesting_count
            stats["irrelevant"] += irrelevant_count

            stats["by_variant_class"][variant_class] = count

        return stats
