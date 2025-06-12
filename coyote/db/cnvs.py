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
CNVsHandler module for Coyote3
==============================

This module defines the `CNVsHandler` class used for accessing and managing
CNV (Copy Number Variation) data in MongoDB.

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
class CNVsHandler(BaseHandler):
    """
    CNVsHandler class for managing CNV data in MongoDB.

    This class provides methods to interact with the `cnvs` collection,
    including querying, updating, and deleting CNV (Copy Number Variation) data.
    It also supports operations like marking CNVs as interesting, false positives,
    or noteworthy, and managing comments and annotations.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.cnvs_collection)

    def get_sample_cnvs(self, query: dict) -> list[dict | None]:
        """
        Retrieve CNVs for a specific sample based on the provided query.

        Args:
            query (dict): A dictionary containing the query parameters to filter CNVs.

        Returns:
            list[dict | None]: A list of CNVs matching the query, or an empty list if none are found.
        """
        return list(self.get_collection().find(query))

    def get_cnv(self, cnv_id: str) -> dict | None:
        """
        Retrieve a CNV document by its unique identifier.

        Args:
            cnv_id (str): The unique identifier of the CNV document.

        Returns:
            dict | None: The CNV document if found, otherwise None.
        """
        return self.get_collection().find_one({"_id": ObjectId(cnv_id)})

    def get_interesting_sample_cnvs(
        self, sample_id: str, interesting: bool = True
    ) -> list[dict | None]:
        """
        Retrieve CNVs for a specific sample and their interesting status.

        Args:
            sample_id (str): The unique identifier of the sample.
            interesting (bool, optional): Filter CNVs based on their interesting status. Defaults to True.

        Returns:
            list[dict | None]: A list of CNVs matching the sample ID and interesting status.
        """
        return self.get_collection().find(
            {"SAMPLE_ID": sample_id, "interesting": interesting}
        )

    def get_cnv_annotations(self, cnv: str) -> list:
        """
        Retrieve annotations for a specific CNV.

        This method constructs a variant string using the chromosome, start,
        and end positions of the CNV and queries the `annotations_collection`
        for matching annotations. The results are sorted by the creation time.

        Args:
            cnv (str): A dictionary containing CNV details, including `chr`,
                       `start`, and `end` keys.

        Returns:
            list: A list of annotation documents associated with the CNV.
        """
        var = f'{str(cnv["chr"])}:{str(cnv["start"])}-{str(cnv["end"])}'
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

        return annotations_arr

    def mark_interesting_cnv(
        self, cnv_id: str, interesting: bool = True
    ) -> None:
        """
        Mark a CNV as interesting.

        Args:
            cnv_id (str): The unique identifier of the CNV document.
            interesting (bool, optional): Whether to mark the CNV as interesting. Defaults to True.

        Returns:
            None
        """
        self.mark_interesting(cnv_id, interesting)

    def unmark_interesting_cnv(
        self, cnv_id: str, interesting: bool = False
    ) -> None:
        """
        Unmark a CNV as interesting.

        Args:
            cnv_id (str): The unique identifier of the CNV document.
            interesting (bool, optional): Whether to mark the CNV as not interesting. Defaults to False.

        Returns:
            None
        """
        self.mark_interesting(cnv_id, interesting)

    def mark_false_positive_cnv(self, cnv_id: str, fp: bool = True) -> None:
        """
        Mark a CNV as false positive.

        Args:
            cnv_id (str): The unique identifier of the CNV document.
            fp (bool, optional): Whether to mark the CNV as false positive. Defaults to True.

        Returns:
            None
        """
        self.mark_false_positive(cnv_id, fp)

    def unmark_false_positive_cnv(self, cnv_id: str, fp: bool = False) -> None:
        """
        Unmark a CNV as false positive.

        Args:
            cnv_id (str): The unique identifier of the CNV document.
            fp (bool, optional): Whether to mark the CNV as not false positive. Defaults to False.

        Returns:
            None
        """
        self.mark_false_positive(cnv_id, fp)

    def noteworthy_cnv(self, cnv_id: str, noteworthy: bool = True) -> None:
        """
        Mark a CNV as noteworthy.

        Args:
            cnv_id (str): The unique identifier of the CNV document.
            noteworthy (bool, optional): Whether to mark the CNV as noteworthy. Defaults to True.

        Returns:
            None
        """
        self.mark_noteworthy(cnv_id, noteworthy)

    def unnoteworthy_cnv(self, cnv_id: str, noteworthy: bool = False) -> None:
        """
        Unmark a CNV as noteworthy.

        Args:
            cnv_id (str): The unique identifier of the CNV document.
            noteworthy (bool, optional): Whether to mark the CNV as not noteworthy. Defaults to False.

        Returns:
            None
        """
        self.mark_noteworthy(cnv_id, noteworthy)

    def hide_cnvs_comment(self, cnv_id: str, comment_id: str) -> None:
        """
        Hide a comment associated with a specific CNV.

        Args:
            cnv_id (str): The unique identifier of the CNV document.
            comment_id (str): The unique identifier of the comment to hide.

        Returns:
            None
        """
        self.hide_comment(cnv_id, comment_id)

    def unhide_cnvs_comment(self, cnv_id: str, comment_id: str) -> None:
        """
        Unhide a comment associated with a specific CNV.

        Args:
            cnv_id (str): The unique identifier of the CNV document.
            comment_id (str): The unique identifier of the comment to unhide.

        Returns:
            None
        """
        self.unhide_comment(cnv_id, comment_id)

    def add_cnv_comment(self, cnv_id: str, comment_doc: dict) -> None:
        """
        Add a comment to a CNV.

        Args:
            cnv_id (str): The unique identifier of the CNV document.
            comment_doc (dict): A dictionary containing the comment details.

        Returns:
            None
        """
        self.update_comment(cnv_id, comment_doc)

    def hidden_cnv_comments(self, id: str) -> bool:
        """
        Check if there are hidden comments for a specific CNV.

        Args:
            id (str): The unique identifier of the CNV document.

        Returns:
            bool: True if there are hidden comments, False otherwise.
        """
        return self.hidden_comments(id)

    def get_unique_cnv_count(self) -> int:
        """
        Get the count of unique CNVs.

        This method uses MongoDB aggregation to group CNVs by their chromosome (`chr`),
        start, and end positions, and calculates the total number of unique CNVs.

        Returns:
            int: The count of unique CNVs in the collection. Returns 0 if no unique CNVs
            are found or if an error occurs during the aggregation process.
        """
        query = [
            {
                "$group": {
                    "_id": {"chr": "$chr", "start": "$start", "end": "$end"}
                }
            },
            {"$group": {"_id": None, "uniqueCnvCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            if result:
                return result[0].get("uniqueCnvCount", 0)
            else:
                return 0
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return 0

    def delete_sample_cnvs(self, sample_oid: str) -> None:
        """
        Delete CNVs for a specific sample.

        This method removes all CNV documents associated with the given sample ID.

        Args:
            sample_oid (str): The unique identifier of the sample whose CNVs are to be deleted.

        Returns:
            None
        """
        return self.get_collection().delete_many({"SAMPLE_ID": sample_oid})
