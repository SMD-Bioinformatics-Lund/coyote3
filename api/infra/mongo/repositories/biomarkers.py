"""
BiomarkerRepository module for Coyote3
===================================

This module defines the `BiomarkerRepository` class used for accessing and managing
biomarker data in MongoDB.
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
class BiomarkerRepository(BaseRepository):
    """
    The `BiomarkerRepository` class provides methods to manage and interact with
    biomarker data stored in the MongoDB database. It allows retrieving, deleting,
    and processing biomarker information for specific samples.

    This class belongs to the MongoDB infrastructure layer and extends the functionality
    of the `BaseRepository` class.
    """

    def __init__(self, adapter):
        """
        Initialize the repository with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.biomarkers_collection)

    def ensure_indexes(self) -> None:
        """Ensure indexes.

        Returns:
            None.
        """
        col = self.get_collection()
        col.create_index(
            [("biomarker_id", 1)],
            name="biomarker_id_1",
            unique=True,
            background=True,
            partialFilterExpression={"biomarker_id": {"$exists": True, "$type": "string"}},
        )
        col.create_index([("SAMPLE_ID", 1)], name="sample_id_1", background=True)

    def get_sample_biomarkers_doc(self, sample_id: str, _normal: bool = False):
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

    def get_sample_biomarkers(self, sample_id: str, _normal: bool = False):
        """
        Get biomarker data for a sample while retaining its report identity and name.

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
        return self.get_collection().find({"SAMPLE_ID": sample_id}, {"SAMPLE_ID": 0})

    def get_samples_biomarkers(self, sample_ids: list[str]) -> dict[str, list[dict]]:
        """Return biomarker documents grouped by sample using one MongoDB query."""
        normalized_ids = list(
            dict.fromkeys(str(sample_id) for sample_id in sample_ids if sample_id)
        )
        grouped: dict[str, list[dict]] = {sample_id: [] for sample_id in normalized_ids}
        if not normalized_ids:
            return grouped
        for document in self.get_collection().find(
            {"SAMPLE_ID": {"$in": normalized_ids}},
            {"_id": 0},
        ):
            sample_id = str(document.get("SAMPLE_ID") or "")
            if sample_id in grouped:
                grouped[sample_id].append(document)
        return grouped

    def delete_sample_biomarkers(self, sample_id: str) -> OperationResult:
        """
        Delete biomarkers data for a sample.

        This method removes all biomarker documents associated with the specified
        sample ID from the `biomarkers` collection in MongoDB.

        Args:
            sample_id (str): The unique identifier of the sample whose biomarkers
                             data should be deleted.

        Returns:
            Structured write result for the delete.
        """
        return OperationResult.from_delete(
            self.get_collection().delete_many({"SAMPLE_ID": sample_id})
        )
