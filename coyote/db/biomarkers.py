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
BiomarkerHandler module for Coyote3
===================================

This module defines the `BiomarkerHandler` class used for accessing and managing
biomarker data in MongoDB.
It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class BiomarkerHandler(BaseHandler):
    """
    The `BiomarkerHandler` class provides methods to manage and interact with
    biomarker data stored in the MongoDB database. It allows retrieving, deleting,
    and processing biomarker information for specific samples.

    This class is part of the `coyote.db` package and extends the functionality
    of the `BaseHandler` class.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.biomarkers_collection)

    def get_sample_biomarkers_doc(self, sample_id: str, normal: bool = False):
        """
        Retrieve the full biomarkers document for a given sample.

        This method queries the `biomarkers` collection in MongoDB to retrieve
        the complete document associated with the specified sample ID.

        Args:
            sample_id (str): The unique identifier of the sample.
            normal (bool, optional): A flag indicating whether to include normal
                                     biomarkers. Defaults to False.

        Returns:
            pymongo.cursor.Cursor: A cursor pointing to the matching document(s)
                                   in the `biomarkers` collection.
        """
        return self.get_collection().find({"SAMPLE_ID": sample_id})

    def get_sample_biomarkers(self, sample_id: str, normal: bool = False):
        """
        Get biomarkers data for a sample excluding `_id`, `name`, and `SAMPLE_ID`.

        This method queries the `biomarkers` collection in MongoDB to retrieve biomarker
        data for a specific sample. The returned data excludes the `_id`, `name`, and
        `SAMPLE_ID` fields.

        Args:
            sample_id (str): The unique identifier of the sample.
            normal (bool, optional): A flag indicating whether to include normal
                                     biomarkers. Defaults to False.

        Returns:
            pymongo.cursor.Cursor: A cursor pointing to the matching document(s)
                                   in the `biomarkers` collection, excluding the
                                   specified fields.
        """
        return self.get_collection().find(
            {"SAMPLE_ID": sample_id}, {"_id": 0, "name": 0, "SAMPLE_ID": 0}
        )

    def delete_sample_biomarkers(self, sample_id: str):
        """
        Delete biomarkers data for a sample.

        This method removes all biomarker documents associated with the specified
        sample ID from the `biomarkers` collection in MongoDB.

        Args:
            sample_id (str): The unique identifier of the sample whose biomarkers
                             data should be deleted.

        Returns:
            pymongo.results.DeleteResult: The result of the delete operation, which
                                          includes details such as the number of
                                          documents deleted.
        """
        return self.get_collection().delete_many({"SAMPLE_ID": sample_id})
