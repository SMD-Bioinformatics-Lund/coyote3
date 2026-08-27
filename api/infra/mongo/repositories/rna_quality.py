"""
RNAQCRepository module for Coyote3
====================================

This module defines the `RNAQCRepository` class used for accessing and managing
qc data in MongoDB.

It is part of the MongoDB infrastructure layer.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.contracts.operations import OperationResult
from api.infra.mongo.repositories.base import BaseRepository


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class RNAQCRepository(BaseRepository):
    """
    Handler for accessing and managing RNA quality control data in MongoDB.
    This class extends the `BaseRepository` to provide specific methods for
    interacting with the RNA QC collection.
    """

    def __init__(self, adapter):
        """
        Initialize the repository with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.rna_qc_collection)

    def ensure_indexes(self) -> None:
        """Ensure indexes.

        Returns:
            None.
        """
        col = self.get_collection()
        col.create_index(
            [("rna_qc_id", 1)],
            name="rna_qc_id_1",
            unique=True,
            background=True,
            partialFilterExpression={"rna_qc_id": {"$exists": True, "$type": "string"}},
        )
        col.create_index([("SAMPLE_ID", 1)], name="sample_id_1", background=True)

    def get_rna_qc(self, sample_id: str) -> dict:
        """
        Retrieve qc data for a sample.

        This method queries the `rna_qc` collection in the database to find
        qc data for the provided.

        Args:
            sample_id (str): Sample id to retrieve qc data for that sample.

        Returns:
            dict: qc data for the specified sample.
        """
        doc = self.get_collection().find_one({"SAMPLE_ID": sample_id})

        if not doc:
            return {}

        doc.pop("_id", None)
        return doc

    def delete_sample_qc(self, sample_oid: str) -> OperationResult:
        """Delete quality-control documents owned by a sample."""
        return OperationResult.from_delete(
            self.get_collection().delete_many({"SAMPLE_ID": sample_oid})
        )
