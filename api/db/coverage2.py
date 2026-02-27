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
CoverageHandler2 module for Coyote3
===================================

This module defines the `CoverageHandler2` class used for accessing and managing
d4 coverage data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.db.base import BaseHandler
from api.runtime import app


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class CoverageHandler2(BaseHandler):
    """
    A handler class for managing d4 coverage data in the database.

    This class provides methods to interact with the `coverage2` collection in MongoDB,
    allowing for efficient retrieval and deletion of coverage data associated with specific samples.

    It acts as an interface between the application and the database, ensuring proper
    handling of d4 coverage data for downstream analysis and reporting.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.coverage2_collection)

    def get_sample_coverage(self, sample_name: str) -> dict:
        """
        Retrieve coverage data for a specific sample.

        This method queries the `coverage2` collection in the database to find
        coverage data for the provided sample name.

        Args:
            sample_name (str): The name of the sample to retrieve coverage data for.

        Returns:
            dict: A dictionary containing the coverage data for the sample, or None
            if no data is found.
        """
        app.logger.debug(sample_name)
        coverage = self.get_collection().find_one({"SAMPLE_ID": sample_name})
        return coverage

    def delete_sample_coverage(self, sample_oid: str):
        """
        Delete coverage data for a sample.

        This method deletes all coverage data in the `coverage2` collection
        for the provided sample ID.

        Args:
            sample_oid (str): The ID of the sample whose coverage data is to be deleted.

        Returns:
            pymongo.results.DeleteResult: The result of the delete operation, which includes
            details such as the number of documents deleted.
        """
        return self.get_collection().delete_many({"SAMPLE_ID": sample_oid})
