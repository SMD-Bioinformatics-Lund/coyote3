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
FusionsHandler module for Coyote3
=================================

This module defines the `FusionsHandler` class used for accessing and managing
fusion data in MongoDB.

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
class FusionsHandler(BaseHandler):
    """
    A handler class for managing fusion data in the database.

    This class provides methods to interact with the `fusions` collection in MongoDB,
    allowing for operations such as retrieving, updating, and deleting fusion records.
    It also includes functionality for handling annotations, comments, classifications,
    and managing false positive statuses for fusion variants.

    The class is designed to extend the base handler functionality and provide
    specialized methods for fusion-related data management.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.fusions_collection)

    def get_sample_fusions(self, query: dict) -> Any:
        """
        Retrieve fusions based on a constructed query.

        This method queries the `fusions` collection in the database using the provided
        query dictionary to retrieve matching fusion records.

        Args:
            query (dict): A dictionary representing the query to filter fusion records.

        Returns:
            Any: A cursor object containing the matching fusion records.
        """
        return self.adapter.fusions_collection.find(query)

    def get_selected_fusioncall(self, fusion: list) -> dict:
        """
        Retrieve the selected fusion call from the fusion data.

        This method iterates through the `calls` field of the fusion data to find
        and return the call marked as selected. A call is considered selected if
        its `selected` field is set to 1.

        Args:
            fusion (list): A list containing fusion call data.

        Returns:
            dict: The selected fusion call if found, otherwise None.
        """
        for call in fusion.get("calls", []):
            if call.get("selected") == 1:
                return call
        return None  # type: ignore

    def get_fusion_annotations(self, fusion: list) -> tuple:
        """
        Retrieve annotations and the latest classification for a given fusion.

        This method processes the fusion data to extract annotations and determine
        the most recent classification based on the `annotations_collection`.

        Returns:
            tuple: A tuple containing:
                - annotations_list (list): A list of annotation documents.
                - latest_classification (dict): The most recent classification document.
        """
        selected_call = self.get_selected_fusioncall(fusion)
        if (
            selected_call
            and "breakpoint1" in selected_call
            and "breakpoint2" in selected_call
        ):
            variant = f"{selected_call['breakpoint1']}^{selected_call['breakpoint2']}"
            annotations_cursor = self.adapter.annotations_collection.find(
                {"variant": variant}
            ).sort("time_created", 1)
        else:
            annotations_cursor = []

        latest_classification = {"class": 999}
        annotations_list = []

        for annotation in annotations_cursor:
            if "class" in annotation:
                latest_classification = annotation
            elif "text" in annotation:
                annotations_list.append(annotation)
        return annotations_list, latest_classification

    def get_fusion(self, id: str) -> dict:
        """
        Retrieve a fusion variant by its ID.

        This method queries the `fusions` collection in the database to find
        a specific fusion variant using its unique ObjectId.

        Args:
            id (str): The ObjectId of the fusion variant to retrieve.

        Returns:
            dict: The fusion variant document if found, otherwise None.
        """
        return self.get_collection().find_one({"_id": ObjectId(id)})

    def get_unique_fusion_count(self) -> int:
        """
        Get the count of unique fusions.

        This method aggregates the `fusions` collection to calculate the number of unique
        fusion records based on their `genes` field.

        Returns:
            int: The count of unique fusions in the collection.
        """
        query = [
            {"$group": {"_id": {"genes": "$genes"}}},
            {"$group": {"_id": None, "uniqueFusionCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            if result:
                return result[0].get("uniqueFusionCount", 0)
            else:
                return 0
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return 0

    def mark_false_positive_fusion(
        self, fusion_id: str, fp: bool = True
    ) -> None:
        """
        Mark the false positive status of a fusion variant.

        This method updates the `fusions` collection to set the false positive status
        of a specific fusion record.

        Args:
            fusion_id (str): The ObjectId of the fusion record to update.
            fp (bool, optional): The false positive status to set. Defaults to `True`.

        Returns:
            None
        """
        self.mark_false_positive(fusion_id, fp)

    def unmark_false_positive_fusion(
        self, fusion_id: str, fp: bool = False
    ) -> None:
        """
        Unmark the false positive status of a fusion variant.

        This method updates the `fusions` collection to set the false positive status
        of a specific fusion record to `False`.

        Args:
            fusion_id (str): The ObjectId of the fusion record to update.
            fp (bool, optional): The false positive status to set. Defaults to `False`.

        Returns:
            None
        """
        self.mark_false_positive(fusion_id, fp)

    def pick_fusion(self, id, callidx, num_calls) -> Any:
        """
        Pick a specific fusion call and mark it as selected.

        This method updates the `calls` field of a fusion record in the `fusions` collection
        to mark a specific call as selected while unselecting all other calls.

        Args:
            id (str): The ObjectId of the fusion record to update.
            callidx (int): The index of the call to mark as selected (1-based index).
            num_calls (int): The total number of calls in the fusion record.

        Returns:
            None
        """
        for i in range(int(num_calls)):
            self.get_collection().update(
                {"_id": ObjectId(id)},
                {"$set": {"calls." + str(i) + ".selected": 0}},
            )

        self.get_collection().update(
            {"_id": ObjectId(id)},
            {"$set": {"calls." + str(int(callidx) - 1) + ".selected": 1}},
        )

    def hide_fus_comment(self, id: str, comment_id: str) -> None:
        """
        Hide a comment for a specific fusion variant.

        This method updates the `fusions` collection to hide a comment associated
        with the specified fusion record.

        Args:
            id (str): The ObjectId of the fusion record containing the comment.
            comment_id (str): The ObjectId of the comment to be hidden.

        Returns:
            None
        """
        self.hide_comment(id, comment_id)

    def unhide_fus_comment(self, id: str, comment_id: str) -> None:
        """
        Unhide a comment for a specific fusion variant.

        This method updates the `fusions` collection to unhide a previously
        hidden comment associated with the specified fusion record.

        Args:
            id (str): The ObjectId of the fusion record containing the comment.
            comment_id (str): The ObjectId of the comment to be unhidden.

        Returns:
            None
        """
        self.unhide_comment(id, comment_id)

    def add_fusion_comment(self, id: str, comment: dict) -> None:
        """
        Add a comment to a specific fusion variant.

        This method updates the `fusions` collection by adding a comment
        to the specified fusion record.

        Args:
            id (str): The ObjectId of the fusion record to which the comment will be added.
            comment (dict): A dictionary containing the comment details.

        Returns:
            None
        """
        self.update_comment(id, comment)

    def delete_sample_fusions(self, sample_oid: str) -> None:
        """
        Delete all fusions associated with a specific sample.

        This method removes all fusion records from the `fusions` collection
        that are linked to the provided sample object ID.

        Args:
            sample_oid (str): The ObjectId of the sample whose fusions are to be deleted.

        Returns:
            None
        """
        return self.get_collection().delete_many({"sample": sample_oid})
