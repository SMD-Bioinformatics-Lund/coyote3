# -*- coding: utf-8 -*-
"""
AnnotationsHandler module for Coyote3
=====================================

This module defines the `AnnotationsHandler` class used for accessing and managing
annotation data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler
from datetime import datetime
from pymongo.results import DeleteResult
from flask import flash
from flask_login import current_user
from typing import Any


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

    def get_global_annotations(
        self, variant: dict, assay: str, subpanel: str
    ) -> tuple:
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
            assay (str): The type of assay being used (e.g., 'solid').
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
        genomic_location = f"{str(variant['CHROM'])}:{str(variant['POS'])}:{variant['REF']}/{variant['ALT']}"
        selected_CSQ = variant["INFO"]["selected_CSQ"]
        if len(selected_CSQ["HGVSp"]) > 0:
            annotations = (
                self.get_collection()
                .find(
                    {
                        "gene": selected_CSQ["SYMBOL"],
                        "$or": [
                            {
                                "nomenclature": "p",
                                "variant": selected_CSQ["HGVSp"],
                            },
                            {
                                "nomenclature": "c",
                                "variant": selected_CSQ["HGVSc"],
                            },
                            {"nomenclature": "g", "variant": genomic_location},
                        ],
                    }
                )
                .sort("time_created", 1)
            )
        elif len(selected_CSQ["HGVSc"]) > 0:
            annotations = (
                self.get_collection()
                .find(
                    {
                        "gene": selected_CSQ["SYMBOL"],
                        "$or": [
                            {
                                "nomenclature": "c",
                                "variant": selected_CSQ["HGVSc"],
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
                .find({"nomenclature": "g", "variant": genomic_location})
                .sort("time_created", 1)
            )

        latest_classification = {"class": 999}
        latest_classification_other = {}
        annotations_arr = []
        annotations_interesting = {}

        for anno in annotations:
            if "class" in anno:
                anno["class"] = int(anno["class"])
                ## collect latest for current assay (if latest not assigned pick that)
                ## also collect latest anno for all other assigned assays (including non-assays)
                ## special rule for assays with subpanels, solid, tumwgs maybe lymph?
                try:
                    if assay == "solid":
                        if (
                            anno["assay"] == assay
                            and anno["subpanel"] == subpanel
                        ):
                            latest_classification = anno
                        else:
                            ass_sub = f"{anno['assay']}:{anno['subpanel']}"
                            latest_classification_other[ass_sub] = anno[
                                "class"
                            ]
                    else:
                        if anno["assay"] == assay:
                            latest_classification = anno
                        else:
                            ass_sub = f"{anno['assay']}:{anno['subpanel']}"
                            latest_classification_other[ass_sub] = anno[
                                "class"
                            ]
                except:
                    latest_classification = None
                    latest_classification_other[
                        f"{anno.get('assay', 'NA')}:{anno.get('subpanel', 'NA')}"
                    ] = anno["class"]
            elif "text" in anno:
                try:
                    if assay == "solid":
                        if (
                            anno["assay"] == assay
                            and anno["subpanel"] == subpanel
                        ):
                            ass_sub = f"{anno['assay']}:{anno['subpanel']}"
                            annotations_interesting[ass_sub] = anno
                            annotations_arr.append(anno)
                        else:
                            annotations_arr.append(anno)
                    else:
                        if anno["assay"] == assay:
                            annotations_interesting[anno["assay"]] = anno
                            annotations_arr.append(anno)
                        else:
                            annotations_arr.append(anno)
                except:
                    annotations_arr.append(anno)

        latest_other_arr = []
        for latest_assay in latest_classification_other:
            assay_sub = latest_assay.split(":")
            latest_other_arr.append(
                {
                    "assay": assay_sub[0],
                    "class": latest_classification_other[latest_assay],
                    "subpanel": assay_sub[1],
                }
            )

        return (
            annotations_arr,
            latest_classification,
            latest_other_arr,
            annotations_interesting,
        )

    def get_additional_classifications(
        self, variant: dict, assay: str, subpanel: str
    ) -> list:
        """
        Retrieve additional classifications for a given variant based on specified assay and subpanel.
        This method constructs a query to search for classifications in the database that match the
        provided variant's genes, transcripts, and nomenclature variants (HGVSp and HGVSc). If the
        assay type is 'solid', it further filters the results by assay and subpanel.
        Args:
            variant (dict): A dictionary containing variant details including 'transcripts', 'HGVSp',
                            'HGVSc', and 'genes'.
            assay (str): The type of assay being used (e.g., 'solid').
            subpanel (str): The subpanel identifier for further filtering when assay is 'solid'.
        Returns:
            list: A list of annotations that match the query criteria, sorted by the time they were created.

        """
        transcripts = variant["transcripts"]
        transcript_patterns = [
            f"^{transcript}(\\..*)?$" for transcript in transcripts
        ]
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
            "assay": assay,
            "class": {"$exists": True},
        }
        if assay == "solid":
            query["subpanel"] = subpanel

        return list(
            self.get_collection().find(query).sort("time_created", -1).limit(1)
        )

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
            "time_created": datetime.now(),
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

        if self.get_collection().insert_one(document):
            flash("Variant classified", "green")
        else:
            flash("Variant classification failed", "red")

        return None

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
        num_assay = list(
            self.get_collection().find(
                {
                    "class": {"$exists": True},
                    "variant": variant,
                    "assay": variant_data.get("assay_group", None),
                    "gene": variant_data.get("gene", None),
                    "nomenclature": nomenclature,
                    "subpanel": variant_data.get("subpanel", None),
                }
            )
        )
        ## If variant has no match to current assay, it has an historical variant, i.e. not assigned to an assay. THIS IS DANGEROUS, maybe limit to admin?
        if len(num_assay) == 0 and current_user.is_admin:
            per_assay = list(
                self.get_collection().find(  # may be change it to delete later
                    {
                        "class": {"$exists": True},
                        "variant": variant,
                        "gene": variant_data.get("gene", None),
                        "nomenclature": nomenclature,
                    }
                )
            )
        else:
            per_assay = self.get_collection().delete_many(
                {
                    "class": {"$exists": True},
                    "variant": variant,
                    "assay": variant_data.get("assay", None),
                    "gene": variant_data.get("gene", None),
                    "nomenclature": nomenclature,
                    "subpanel": variant_data.get("subpanel", None),
                }
            )

        return per_assay

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
        return (
            self.get_collection()
            .find({"gene": gene_name})
            .sort("time_created", 1)
        )

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
        return tuple(
            self.get_collection().aggregate(assay_class_stats_pipeline)
        )

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
