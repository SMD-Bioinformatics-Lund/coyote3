#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

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
from bson.objectid import ObjectId
from coyote.db.base import BaseHandler
from flask import current_app as app
from typing import Any


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

    # TODO: This will be removed once the sample ids are set in the sample doc
    def get_sample_ids(self, sample_id: str) -> dict:
        """
        Retrieve sample IDs and their associated types for a given sample ID.

        Args:
            sample_id (str): The ID of the sample to retrieve.

        Returns:
            dict: A dictionary where the keys are types (e.g., "type1", "type2")
                and the values are the corresponding sample IDs.
        """
        a_var = self.get_collection().find_one(
            {"SAMPLE_ID": sample_id}, {"GT": 1}
        )
        ids = {}
        if a_var:
            for gt in a_var["GT"]:
                ids[gt.get("type")] = gt.get("sample")
        return ids

    # TODO: This will be removed once the sample num is set in the sample doc
    def get_gt_lengths_by_sample_ids(
        self, sample_ids: list[str]
    ) -> dict[str, int]:
        """
        For each SAMPLE_ID, fetch one document and get the length of the 'GT' field (a list).

        Args:
            sample_ids (list[str]): List of SAMPLE_IDs to look up.

        Returns:
            dict[str, int]: Mapping of SAMPLE_ID to length of GT array.
        """
        pipeline = [
            {"$match": {"SAMPLE_ID": {"$in": sample_ids}}},
            {"$sort": {"_id": 1}},
            {"$group": {"_id": "$SAMPLE_ID", "GT": {"$first": "$GT"}}},
        ]
        results = self.get_collection().aggregate(pipeline)
        return {
            r["_id"]: len(r["GT"]) if isinstance(r.get("GT"), list) else 0
            for r in results
        }

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
        current_sample_id = variant["SAMPLE_ID"]
        simple_id = variant["simple_id"]

        # Step 1: Fetch up to 20 variants with the same simple_id but from other samples
        variants = list(
            self.get_collection()
            .find(
                {
                    "simple_id": simple_id,
                    "SAMPLE_ID": {"$ne": current_sample_id},
                },
                {
                    "_id": 1,
                    "SAMPLE_ID": 1,
                    "simple_id": 1,
                    "GT": 1,
                    "fp": 1,
                    "interesting": 1,
                    "irrelevant": 1,
                },
            )
            .limit(20)
        )

        # Step 2: Collect only the sample ObjectIds we need
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

        # Step 4: Attach GT to each sample_info
        results = []
        for v in variants:
            sid = v["SAMPLE_ID"]
            info = sample_map.get(
                sid, {"sample_name": "unknown", "assay": "unknown"}
            )
            info["GT"] = v.get("GT")
            info["fp"] = v.get("fp", False)  # Add fp status if available
            info["interesting"] = v.get(
                "interesting", False
            )  # Add interesting status if available
            info["irrelevant"] = v.get(
                "irrelevant", False
            )  # Add irrelevant status if available
            results.append(info)

        return results

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
        self.mark_false_positive(variant_id, fp)

    def unmark_false_positive_var(
        self, variant_id: str, fp: bool = False
    ) -> Any:
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
        self.mark_false_positive(variant_id, fp)

    def mark_false_positive_var_bulk(
        self, variant_ids: list[str], fp: bool = True
    ) -> Any:
        """
        Mark multiple variants as false positive.

        Args:
            variant_ids (list[str]): List of variant document IDs.
            fp (bool, optional): The false positive status to set. Defaults to True.

        Returns:
            Any: The result of the bulk update operation.
        """
        return self.mark_false_positive_bulk(variant_ids, fp)

    def unmark_false_positive_var_bulk(
        self, variant_ids: list[str], fp: bool = False
    ) -> Any:
        """
        Unmark multiple variants as false positive.

        Args:
            variant_ids (list[str]): List of variant document IDs.
            fp (bool, optional): The false positive status to set. Defaults to False.

        Returns:
            Any: The result of the bulk update operation.
        """
        return self.mark_false_positive_bulk(variant_ids, fp)

    def mark_interesting_var(
        self, variant_id: str, interesting: bool = True
    ) -> Any:
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

    def unmark_interesting_var(
        self, variant_id: str, interesting: bool = False
    ) -> Any:
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

    def mark_irrelevant_var(
        self, variant_id: str, irrelevant: bool = True
    ) -> Any:
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

    def unmark_irrelevant_var(
        self, variant_id: str, irrelevant: bool = False
    ) -> Any:
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

    def mark_irrelevant_var_bulk(
        self, variant_ids: list[str], irrelevant: bool = True
    ) -> Any:
        """
        Mark multiple variants as irrelevant.

        Args:
            variant_ids (list[str]): List of variant document IDs.
            irrelevant (bool, optional): The status to set. Defaults to True.
        """
        return self.mark_irrelevant_bulk(variant_ids, irrelevant)

    def unmark_irrelevant_var_bulk(
        self, variant_ids: list[str], irrelevant: bool = False
    ) -> Any:
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
        return self.get_collection().find().count()

    def get_unique_total_variant_counts(self) -> int:
        """
        Get the count of all unique variants in the collection.

        This method uses MongoDB aggregation to group variants by their unique
        chromosome (CHROM), position (POS), reference allele (REF), and alternate allele (ALT).
        It then counts the total number of unique groups.

        Returns:
            int: The total count of unique variants in the collection.
        """
        return len(self.get_collection().distinct("simple_id")) or 0

    def get_unique_snp_count(self) -> int:
        """
        Get the count of unique SNP (Single Nucleotide Polymorphism) variants.

        This method retrieves all unique variant `simple_id`s where the `variant_class` is "SNV"
        (Single Nucleotide Variant), which typically represents SNPs, and returns their count.

        Returns:
            int: The number of unique SNP variants in the collection.
        """
        snp_ids = self.get_collection().distinct(
            "simple_id", {"variant_class": "SNV"}
        )
        return len(snp_ids) or 0

    def get_unique_fp_count(self) -> int:
        """
        Get the count of unique false positive variants.

        Returns:
            int: The number of unique variants marked as false positive in the collection.
        """
        fps = self.get_collection().distinct("simple_id", {"fp": True})
        return len(fps) or 0

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
        return self.get_collection().delete_many({"SAMPLE_ID": sample_oid})
