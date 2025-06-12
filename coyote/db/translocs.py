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
TranslocsHandler module for Coyote3
===================================

This module defines the `TranslocsHandler` class used for accessing and managing
translocation data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from bson.objectid import ObjectId
from coyote.db.base import BaseHandler
from flask import current_app as app


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class TranslocsHandler(BaseHandler):
    """
    TranslocsHandler is a class for managing translocation data in the database.

    This class provides methods to perform CRUD operations, manage comments,
    and handle specific flags (e.g., `interesting`, `false positive`) for translocations.
    It also includes utility methods for retrieving annotations, counting unique translocations,
    and deleting translocations associated with a sample.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.transloc_collection)

    def get_sample_translocations(self, sample_id: str) -> list:
        """
        Retrieve all translocations for a given sample.

        Args:
            sample_id (str): The unique identifier of the sample.

        Returns:
            list: A list of translocations matching the sample ID.
        """
        return list(self.get_collection().find({"SAMPLE_ID": sample_id}))

    def get_interesting_sample_translocations(
        self, sample_id: str, interesting: bool = True
    ) -> list:
        """
        Retrieve translocations marked as interesting for a given sample.

        Args:
            sample_id (str): The unique identifier of the sample.
            interesting (bool, optional): Filter for translocations marked as interesting. Defaults to True.

        Returns:
            list: A list of translocations matching the sample ID and interesting flag.
        """
        return list(
            self.get_collection().find(
                {"SAMPLE_ID": sample_id, "interesting": interesting}
            )
        )

    def get_transloc(self, transloc_id: str) -> dict:
        """
        Retrieve a translocation document by its unique identifier.

        Args:
            transloc_id (str): The unique identifier of the translocation.

        Returns:
            dict: A dictionary representing the translocation document if found, or None if no document matches the given ID.

        Raises:
            bson.errors.InvalidId: If the provided `transloc_id` is not a valid ObjectId.
        """
        return self.get_collection().find_one({"_id": ObjectId(transloc_id)})

    def get_transloc_annotations(self, tl: dict) -> list:
        """
        Retrieve annotations for a given translocation.

        Args:
            tl (dict): A dictionary representing the translocation, containing keys such as "CHROM", "POS", and "ALT".

        Returns:
            dict: A list of annotation dictionaries associated with the translocation. Each annotation may include
            classification or textual information.
        """
        var = f'{str(tl["CHROM"])}:{str(tl["POS"])}^{tl["ALT"]}'
        annotations = self.adapter.annotations_collection.find(
            {"variant": var}
        ).sort("time_created", 1)

        latest_classification = {"class": 999}
        annotations_arr = []
        for anno in annotations:
            if "class" in anno:
                latest_classification = anno
            elif "text" in anno:
                annotations_arr.append(anno)

        return annotations_arr  # , latest_classification

    def mark_interesting_transloc(
        self, transloc_id: str, interesting: bool = True
    ) -> None:
        """
        Mark or unmark a translocation as interesting.

        Args:
            transloc_id (str): The unique identifier of the translocation.
            interesting (bool, optional): A flag indicating whether to mark the translocation as interesting. Defaults to True.

        Returns:
            None
        """
        self.mark_interesting(transloc_id, interesting)

    def unmark_interesting_transloc(
        self, transloc_id: str, interesting: bool = False
    ) -> None:
        """
        Unmark a translocation as interesting.

        This method updates the `interesting` flag for a translocation to `False`.

        Args:
            transloc_id (str): The unique identifier of the translocation.
            interesting (bool, optional): A flag indicating whether to mark the translocation as interesting. Defaults to False.

        Returns:
            None
        """
        self.mark_interesting(transloc_id, interesting)

    def mark_false_positive_transloc(
        self, transloc_id: str, fp: bool = True
    ) -> None:
        """
        Mark translocations as false positives.
        This method updates the `fp` (false positive) flag for a translocation.

        Args:
            transloc_id (str): The unique identifier of the translocation.
            fp (bool, optional): A flag indicating whether to mark the translocation as a false positive. Defaults to True.

        Returns:
            None
        """
        self.mark_false_positive(transloc_id, fp)

    def unmark_false_positive_transloc(
        self, transloc_id: str, fp: bool = False
    ) -> None:
        """
        Unmark translocations as false positives.
        This method updates the `fp` (false positive) flag for a translocation.

        Args:
            transloc_id (str): The unique identifier of the translocation.
            fp (bool, optional): A flag indicating whether to unmark the translocation as a false positive. Defaults to False.

        Returns:
            None
        """
        self.mark_false_positive(transloc_id, fp)

    def hide_transloc_comment(self, transloc_id: str, comment_id: str) -> None:
        """
        Hide a comment associated with a specific translocation.

        This method updates the visibility status of a comment linked to a translocation,
        effectively hiding it from view.

        Args:
            transloc_id (str): The unique identifier of the translocation.
            comment_id (str): The unique identifier of the comment to be hidden.

        Returns:
            None
        """
        self.hide_comment(transloc_id, comment_id)

    def unhide_transloc_comment(
        self, transloc_id: str, comment_id: str
    ) -> None:
        """
        Unhide a comment associated with a specific translocation.

        This method updates the visibility status of a comment linked to a translocation,
        making it visible again.

        Args:
            transloc_id (str): The unique identifier of the translocation.
            comment_id (str): The unique identifier of the comment to be unhidden.

        Returns:
            None
        """
        self.unhide_comment(transloc_id, comment_id)

    def add_transloc_comment(self, transloc_id: str, comment: dict) -> None:
        """
        Add a new comment to a specific translocation.

        This method associates a new comment with a translocation by updating the
        translocation's comment data.

        Args:
            transloc_id (str): The unique identifier of the translocation.
            comment (dict): The content of the comment to be added.

        Returns:
            None
        """
        self.update_comment(transloc_id, comment)

    def hidden_transloc_comments(self, id: str) -> bool:
        """
        Check if there are hidden comments for a specific translocation.

        This method determines whether any comments associated with a translocation
        are currently hidden.

        Args:
            id (str): The unique identifier of the translocation.

        Returns:
            bool: Returns `True` if there are hidden comments, otherwise `False`.
        """
        return self.hidden_comments(id)

    def get_unique_transloc_count(self) -> list:
        """
        Get the count of unique translocations.

        This method aggregates translocation data to calculate the number of unique
        translocations based on their `CHROM`, `POS`, `REF`, and `ALT` fields.

        Returns:
            int: The count of unique translocations.
        """
        query = [
            {
                "$group": {
                    "_id": {
                        "CHROM": "$CHROM",
                        "POS": "$POS",
                        "REF": "$REF",
                        "ALT": "$ALT",
                    }
                }
            },
            {"$group": {"_id": None, "uniqueTranslocCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            if result:
                return result[0].get("uniqueTranslocCount", 0)
            else:
                return 0
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return 0

    def delete_sample_translocs(self, sample_oid: str) -> None:
        """
        Delete all translocations associated with a specific sample.

        This method removes all translocation documents from the collection
        that match the given sample's unique identifier.

        Args:
            sample_oid (str): The unique identifier (ObjectId) of the sample.

        Returns:
            None
        """
        return self.get_collection().delete_many({"SAMPLE_ID": sample_oid})
