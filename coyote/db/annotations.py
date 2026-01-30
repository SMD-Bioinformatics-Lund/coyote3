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
AnnotationsHandler module for Coyote3
=====================================

This module defines the `AnnotationsHandler` class used for accessing and managing
annotation data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

from copy import deepcopy

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler
from datetime import datetime
from pymongo.results import DeleteResult
from flask import flash
from flask_login import current_user
from typing import Any, Dict, Tuple, List, Optional
from urllib.parse import unquote
from coyote.util.common_utility import CommonUtility
from collections import defaultdict


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class AnnotationsHandler(BaseHandler):
    """
    AnnotationsHandler is a class responsible for managing annotation data
    stored in the `coyote["annotations"]` MongoDB collection. It provides
    methods to retrieve, insert, update, and delete annotations, as well as
    to handle classifications and comments related to genetic variants.

    This class serves as a key component for efficiently managing and
    querying annotation-related data in the database.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.annotations_collection)

    def get_annotation_by_oid(self, oid: str) -> dict | None:
        """
        Retrieve an annotation by its ObjectId.

        This method fetches a single annotation document from the MongoDB
        collection using the provided ObjectId.

        Args:
            oid (str): The ObjectId of the annotation to be retrieved.
        Returns:
            dict | None: The annotation document if found, otherwise None.
        """
        return self.get_collection().find_one({"_id": oid})

    def get_annotation_text_by_oid(self, oid: str) -> str | None:
        """
        Retrieve the text of an annotation by its ObjectId.

        This method fetches the 'text' field of a single annotation document
        from the MongoDB collection using the provided ObjectId.

        Args:
            oid (str): The ObjectId of the annotation to be retrieved.

        Returns:
            str | None: The text of the annotation if found, otherwise None.
        """
        annotation = self.get_collection().find_one({"_id": oid}, {"text": 1})
        if annotation:
            return annotation.get("text", None)
        return None

    def insert_annotation_bulk(self, annotations: list) -> Any:
        """
        Insert multiple annotations into the database in bulk.

        This method takes a list of annotation dictionaries and inserts them
        into the MongoDB collection. It is designed for efficiency when
        handling multiple annotations at once.

        Args:
            annotations (list): A list of dictionaries, each representing an
                                annotation to be inserted.

        Returns:
            Any: The result of the insert operation, which may include the
                 inserted document IDs or other relevant information.
        """
        if not annotations:
            return None

        # Create a deep copy to avoid modifying the original list
        annotations_copy = deepcopy(annotations)
        if self.get_collection().insert_many(annotations_copy):
            flash(f"Inserted {len(annotations_copy)} annotations", "green")
            return True
        else:
            flash("Failed to insert annotations", "red")
            return False

    def get_global_annotations(self, variant: dict, assay_group: str, subpanel: str) -> tuple:
        """
        Retrieve global annotations for a given variant, assay, and subpanel.

        This method queries the MongoDB collection for annotations that match
        the provided variant's genomic location, gene symbol, and nomenclature
        (HGVSp, HGVSc, or genomic). It prioritizes annotations based on the
        presence of HGVSp, HGVSc, or genomic location in that order.

        Args:
            variant (dict): A dictionary containing variant details, including
                            'CHROM', 'POS', 'REF', 'ALT', and 'INFO' with
                            'selected_CSQ' data.
            assay_group (str): The type of assay being used (e.g., 'solid').
            subpanel (str): The subpanel identifier for further filtering when
                            assay is 'solid'.

        Returns:
            tuple: A tuple containing:
                - annotations_arr (list): A list of all annotations.
                - latest_classification (dict): The latest classification for
                  the current assay.
                - latest_other_arr (list): A list of classifications for other
                  assays and subpanels.
                - annotations_interesting (dict): A dictionary of annotations
                  deemed interesting based on assay and subpanel.
        """
        try:
            genomic_location = (
                f"{str(variant['CHROM'])}:{str(variant['POS'])}:{variant['REF']}/{variant['ALT']}"
            )
        except KeyError:
            genomic_location = ""
        selected_CSQ = variant["INFO"]["selected_CSQ"]
        hgvsp = unquote(selected_CSQ.get("HGVSp", ""))
        hgvsc = unquote(selected_CSQ.get("HGVSc", ""))

        if len(hgvsp) > 0:
            annotations = (
                self.get_collection()
                .find(
                    {
                        "gene": selected_CSQ["SYMBOL"],
                        "$or": [
                            {
                                "nomenclature": "p",
                                "variant": hgvsp,
                            },
                            {
                                "nomenclature": "c",
                                "variant": hgvsc,
                            },
                            {"nomenclature": "g", "variant": genomic_location},
                        ],
                    }
                )
                .sort("time_created", 1)
            )

        elif len(hgvsc) > 0:
            annotations = (
                self.get_collection()
                .find(
                    {
                        "gene": selected_CSQ["SYMBOL"],
                        "$or": [
                            {
                                "nomenclature": "c",
                                "variant": hgvsc,
                            },
                            {"nomenclature": "g", "variant": genomic_location},
                        ],
                    }
                )
                .sort("time_created", 1)
            )
        else:
            annotations = (
                self.get_collection()
                .find(
                    {
                        "gene": selected_CSQ["SYMBOL"],
                        "nomenclature": "g",
                        "variant": genomic_location,
                    }
                )
                .sort("time_created", 1)
            )

        latest_classification = {"class": 999}
        latest_classification_other = {}
        annotations_arr = []
        annotations_interesting = {}

        for anno in annotations:
            ## collect latest for current assay (if latest not assigned pick that)
            ## also collect latest anno for all other assigned assays (including non-assays)
            ## special rule for assays with subpanels, solid, tumwgs maybe lymph?
            if "class" in anno:
                try:
                    anno["class"] = int(anno["class"])
                    assay = anno["assay"]
                    sub = anno["subpanel"]
                    ass_sub = f"{assay}:{sub}"
                    if assay_group == "solid":
                        if assay == assay_group and sub == subpanel:
                            latest_classification = anno
                        else:
                            latest_classification_other[ass_sub] = anno["class"]
                    else:
                        if assay == assay_group:
                            latest_classification = anno
                        else:
                            latest_classification_other[ass_sub] = anno["class"]
                except KeyError:
                    latest_classification = anno
                    latest_classification_other["N/A"] = anno["class"]
            elif "text" in anno:
                try:
                    assay = anno["assay"]
                    sub = anno["subpanel"]
                    ass_sub = f"{assay}:{sub}"
                    if assay_group == "solid":
                        if assay == assay_group and sub == subpanel:
                            annotations_interesting[ass_sub] = anno
                    elif assay == assay_group:
                        annotations_interesting[assay] = anno
                    annotations_arr.append(anno)
                except KeyError:
                    annotations_arr.append(anno)

        latest_other_arr = []
        for latest_assay in latest_classification_other:
            assay_sub = latest_assay.split(":")
            latest_other_arr.append(
                {
                    "assay": assay_sub[0],
                    "class": latest_classification_other[latest_assay],
                    "subpanel": assay_sub[1] if len(assay_sub) > 1 else None,
                }
            )

        return (
            annotations_arr,
            latest_classification,
            latest_other_arr,
            annotations_interesting,
        )

    def get_additional_classifications(
        self, variant: dict, assay_group: str, subpanel: str
    ) -> list:
        """
        Retrieve additional classifications for a given variant based on specified assay and subpanel.
        This method constructs a query to search for classifications in the database that match the
        provided variant's genes, transcripts, and nomenclature variants (HGVSp and HGVSc). If the
        assay type is 'solid', it further filters the results by assay and subpanel.
        Args:
            variant (dict): A dictionary containing variant details including 'transcripts', 'HGVSp',
                            'HGVSc', and 'genes'.
            assay_group (str): The type of assay being used (e.g., 'solid').
            subpanel (str): The subpanel identifier for further filtering when assay is 'solid'.
        Returns:
            list: A list of annotations that match the query criteria, sorted by the time they were created.

        """
        transcripts = variant["transcripts"]
        transcript_patterns = [f"^{transcript}(\\..*)?$" for transcript in transcripts]
        hgvsp = variant["HGVSp"]
        hgvsc = variant["HGVSc"]
        genes = variant["genes"]
        query = {
            "gene": {"$in": genes},
            "transcript": {"$regex": "|".join(transcript_patterns)},
            "$or": [
                {"nomenclature": "p", "variant": {"$in": hgvsp}},
                {"nomenclature": "c", "variant": {"$in": hgvsc}},
                {"nomenclature": "g", "variant": variant["simple_id"]},
            ],
            "assay": assay_group,
            "class": {"$exists": True},
        }
        if assay_group == "solid":
            query["subpanel"] = subpanel

        return list(self.get_collection().find(query).sort("time_created", -1).limit(1))

    def insert_classified_variant(
        self,
        variant: str,
        nomenclature: str,
        class_num: int,
        variant_data: dict,
        **kwargs,
    ) -> Any:
        """
        Insert a classified variant into the database.

        This method creates a document representing a classified variant and inserts it into the MongoDB collection.
        The document includes details such as the variant, nomenclature, classification, assay, subpanel, and additional
        metadata like the author and creation time.

        Args:
            variant (str): The variant identifier (e.g., genomic location or variant ID).
            nomenclature (str): The nomenclature type ('p', 'c', 'g', or 'f').
            class_num (int): The classification number assigned to the variant.
            variant_data (dict): A dictionary containing additional variant details, such as:
                - assay (str): The assay type (e.g., 'solid').
                - subpanel (str): The subpanel identifier.
                - gene (str): The gene symbol (if applicable).
                - transcript (str): The transcript identifier (if applicable).
                - gene1 (str): The first gene symbol (if nomenclature is 'f').
                - gene2 (str): The second gene symbol (if nomenclature is 'f').
            **kwargs: Additional optional arguments, such as:
                - text (str): A textual comment or description for the variant.

        Returns:
            Any: The result of the insert operation, which may include the inserted document ID or other relevant information.
        """
        document = {
            "author": self.current_user.username,
            "time_created": CommonUtility.utc_now(),
            "variant": variant,
            "nomenclature": nomenclature,
            "assay": variant_data.get("assay_group", None),
            "subpanel": variant_data.get("subpanel", None),
        }

        if "text" in kwargs:
            document["text"] = kwargs["text"]
        else:
            document["class"] = class_num

        if nomenclature != "f":
            document["gene"] = variant_data.get("gene", None)
            document["transcript"] = variant_data.get("transcript", None)
        else:
            document["gene1"] = variant_data.get("gene1", None)
            document["gene2"] = variant_data.get("gene2", None)

        result = self.get_collection().insert_one(document)
        if result:
            flash("Variant classified", "green")
        else:
            flash("Variant classification failed", "red")

        return result

    def delete_classified_variant(
        self, variant: str, nomenclature: str, variant_data: dict
    ) -> list | DeleteResult:
        """
        Delete a classified variant from the database.

        This method removes a classified variant document from the MongoDB collection
        based on the provided variant details, nomenclature, and assay information.
        If the variant is not assigned to the current assay, it checks for historical
        variants and may delete them if the user has admin privileges.

        Args:
            variant (str): The variant identifier (e.g., genomic location or variant ID).
            nomenclature (str): The nomenclature type ('p', 'c', 'g', or 'f').
            variant_data (dict): A dictionary containing additional variant details, such as:
                - assay (str): The assay type (e.g., 'solid').
                - subpanel (str): The subpanel identifier.
                - gene (str): The gene symbol (if applicable).

        Returns:
            list | DeleteResult: A list of matching documents or the result of the delete operation.
        """
        print(variant_data)
        classified_docs = list(
            self.get_collection().find(
                {
                    "class": {"$exists": True},
                    "variant": variant,
                    "assay": variant_data.get("assay_group", None),
                    "gene": variant_data.get("gene", None),
                    "gene1": variant_data.get("gene1", None),  # this is for fusion
                    "gene2": variant_data.get("gene2", None),  # this is for fusion
                    "nomenclature": nomenclature,
                    "subpanel": variant_data.get("subpanel", None),
                }
            )
        )
        ## If variant has no match to current assay, it has an historical variant, i.e. not assigned to an assay. THIS IS DANGEROUS, maybe limit to admin?
        if len(classified_docs) == 0 and current_user.is_admin:
            delete_result = self.get_collection().find(  # may be change it to delete later
                {
                    "class": {"$exists": True},
                    "variant": variant,
                    "gene": variant_data.get("gene", None),
                    "gene1": variant_data.get("gene1", None),  # this is for fusion
                    "gene2": variant_data.get("gene2", None),  # this is for fusion
                    "nomenclature": nomenclature,
                }
            )
        else:
            delete_result = self.get_collection().delete_many(
                {
                    "class": {"$exists": True},
                    "variant": variant,
                    "assay": variant_data.get("assay_group", None),
                    "gene": variant_data.get("gene", None),
                    "gene1": variant_data.get("gene1", None),  # this is for fusion
                    "gene2": variant_data.get("gene2", None),  # this is for fusion
                    "nomenclature": nomenclature,
                    "subpanel": variant_data.get("subpanel", None),
                }
            )

        return delete_result

    def get_gene_annotations(self, gene_name: str) -> list:
        """
        Get all annotations for a given gene.

        This method retrieves all annotations from the MongoDB collection
        that are associated with the specified gene name. The results are
        sorted by the time they were created in ascending order.

        Args:
            gene_name (str): The name of the gene for which annotations
                             are to be retrieved.

        Returns:
            list: A list of annotations related to the specified gene,
                  sorted by creation time.
        """
        return self.get_collection().find({"gene": gene_name}).sort("time_created", 1)

    def add_anno_comment(self, comment: dict) -> Any:
        """
        Add a comment to a variant.

        This method allows adding a comment to a specific variant in the database.
        The comment is expected to be a dictionary containing relevant details
        about the comment, such as the author, timestamp, and the content of the comment.

        Args:
            comment (dict): A dictionary containing the comment details.

        Returns:
            Any: The result of the insert operation
        """
        self.add_comment(comment)

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

    def find_variants_by_search_string(
        self,
        search_str: str,
        search_mode: str,
        include_annotation_text: bool,
        assays: list | None = None,
        limit: int | None = None,
    ) -> list:
        """
        Find variants matching the search string.

        This method searches for variants in the database that match the provided
        search string. It looks for matches in the 'variant', 'gene', and 'transcript'
        fields using case-insensitive regular expressions.

        Args:
            search_str (str): The search string to match against variant fields.
            limit (int | None): Optional limit on the number of results to return.
            search_mode (str): The mode of search, can be 'gene', 'transcript', 'variant', 'author', or 'subpanel'.
            include_annotation_text (bool): Whether to include annotations with text.
            assays (list | None): Optional list of assays to filter the results.

        Returns:
            list: A list of variant documents that match the search criteria.
        """
        if not search_str or search_str == "":
            return []

        if search_mode == "gene":
            query = {"gene": {"$regex": search_str, "$options": "i"}}
        elif search_mode == "transcript":
            query = {"transcript": {"$regex": search_str, "$options": "i"}}
        elif search_mode == "variant":  # variant
            query = {"variant": {"$regex": search_str, "$options": "i"}}
        elif search_mode == "author":
            query = {"author": {"$regex": search_str, "$options": "i"}}
        elif search_mode == "subpanel":
            query = {"subpanel": {"$regex": search_str, "$options": "i"}}
        else:
            return []

        if not include_annotation_text:
            query["text"] = {"$exists": False}

        if assays is not None:
            query["assay"] = {"$in": assays}

        cursor = self.get_collection().find(query).sort("time_created", -1)

        if limit is not None:
            cursor = cursor.limit(limit)
        return list(cursor)

    def get_tier_stats_by_search(
        self,
        search_str: str,
        search_mode: str,
        include_annotation_text: bool,
        assays: Optional[List[str]] = None,
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

        # --- same query logic as find_variants_by_search_string ---
        if search_mode == "gene":
            query = {"gene": {"$regex": search_str, "$options": "i"}}
        elif search_mode == "transcript":
            query = {"transcript": {"$regex": search_str, "$options": "i"}}
        elif search_mode == "variant":
            query = {"variant": {"$regex": search_str, "$options": "i"}}
        elif search_mode == "author":
            query = {"author": {"$regex": search_str, "$options": "i"}}
        elif search_mode == "subpanel":
            query = {"subpanel": {"$regex": search_str, "$options": "i"}}
        else:
            return {"total": {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}, "by_assay": {}}

        if not include_annotation_text:
            query["text"] = {"$exists": False}

        if assays is not None and len(assays) > 0:
            query["assay"] = {"$in": assays}

        query["class"] = {"$exists": True, "$ne": None}

        # --- dedupe keys ---
        # total: dedupe across assays (avoid counting same variant multiple times)
        total_variant_key = {
            "variant": "$variant",
            "gene": "$gene",
            "transcript": "$transcript",
        }

        # by_assay: dedupe within assay (same variant can be re-tiered in same assay)
        per_assay_variant_key = {
            "assay": "$assay",
            "variant": "$variant",
            "gene": "$gene",
            "transcript": "$transcript",
        }

        def _tier_rollup_stage():
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
