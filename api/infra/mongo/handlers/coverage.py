"""
CoverageHandler module for managing coverage data
=================================================

This module provides the `CoverageHandler` class for interacting with
panel-level sample coverage data stored in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from typing import Any

from api.infra.mongo.handlers.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class CoverageHandler(BaseHandler):
    """
    A handler class for managing sample panel coverage data.

    This class provides methods to interact with the configured panel coverage
    collection in MongoDB, allowing retrieval and deletion by sample identifier.

    It acts as an interface between the application and the database, ensuring proper
    handling of coverage data for downstream analysis and reporting.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.coverage_collection)

    def ensure_indexes(self) -> None:
        """Create indexes used by legacy coverage lookup/delete paths."""
        col = self.get_collection()
        col.create_index(
            [("SAMPLE_ID", 1)],
            name="SAMPLE_ID_1",
            background=True,
        )
        col.create_index([("sample", 1)], name="sample_1", background=True)

    def get_sample_coverage(self, sample_id: str) -> dict | None:
        """
        Retrieve coverage data for a specific sample.

        This method queries the panel coverage collection by `SAMPLE_ID`.

        Args:
            sample_id (str): The sample ObjectId value serialized as a string.

        Returns:
            dict | None: Coverage document for the sample, if available.
        """
        return self.get_collection().find_one({"SAMPLE_ID": sample_id})

    def delete_sample_coverage(self, sample_oid: str) -> Any:
        """
        Delete coverage data for a sample.

        This method deletes coverage data for the provided `SAMPLE_ID`.

        Args:
         sample_oid (str): The ID of the sample whose coverage data is to be deleted.

        Returns:
         Any: The result of the delete operation, which includes
         details such as the number of documents deleted.
        """
        return self.get_collection().delete_many({"SAMPLE_ID": sample_oid})
