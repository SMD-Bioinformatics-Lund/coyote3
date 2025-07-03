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
CoverageHandler module for managing coverage data
=================================================

This module provides the `CoverageHandler` class for interacting with and managing
normal low coverage data stored in a MongoDB database.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

from typing import Any

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class CoverageHandler(BaseHandler):
    """
    A handler class for managing normal coverage data in the database.

    This class provides methods to interact with the `coverage` collection in MongoDB,
    allowing for efficient retrieval and deletion of coverage data associated with specific samples.

    It acts as an interface between the application and the database, ensuring proper
    handling of coverage data for downstream analysis and reporting.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.coverage_collection)

    def get_sample_coverage(self, sample_name: str) -> list[dict]:
        """
        Retrieve coverage data for a specific sample.

        This method queries the `coverage` collection in the database to find
        coverage data for the provided sample name.

        Args:
            sample_name (str): The name of the sample to retrieve coverage data for.

        Returns:
            list[dict]: A list of dictionaries containing the coverage data for the sample.
        """
        coverage = self.get_collection().find({"sample": sample_name})
        return list(coverage)

    def delete_sample_coverage(self, sample_oid: str) -> Any:
        """
        Delete coverage data for a sample.

        This method deletes all coverage data in the `coverage` collection
        for the provided sample ID.

        Args:
         sample_oid (str): The ID of the sample whose coverage data is to be deleted.

        Returns:
         Any: The result of the delete operation, which includes
         details such as the number of documents deleted.
        """
        return self.get_collection().delete_many({"sample": sample_oid})
