"""
BlacklistRepository module for Coyote3
===================================

This module defines the `BlacklistRepository` class used for accessing and managing
blacklist data in MongoDB.

It is part of the MongoDB infrastructure layer.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.contracts.operations import OperationResult
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repository_utils import get_simple_id


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class BlacklistRepository(BaseRepository):
    """
    The `BlacklistRepository` class provides methods to manage and interact with
    blacklist data stored in the MongoDB database. It allows adding blacklist
    information to variants, inserting new blacklist entries, and retrieving
    unique blacklist counts.

    This class belongs to the MongoDB infrastructure layer and extends the functionality
    of the `BaseRepository` class.
    """

    def __init__(self, adapter):
        """
        Initialize the repository with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.blacklist_collection)

    def ensure_indexes(self) -> None:
        """
        Create indexes used by blacklist read/write paths and dashboard metrics.
        """
        col = self.get_collection()
        col.create_index(
            [("blacklist_entry_id", 1)],
            name="blacklist_entry_id_1",
            unique=True,
            background=True,
            partialFilterExpression={"blacklist_entry_id": {"$exists": True, "$type": "string"}},
        )
        col.create_index([("assay", 1), ("pos", 1)], name="assay_pos_1", background=True)
        col.create_index([("pos", 1)], name="pos_1", background=True)

    def add_blacklist_data(self, variants: list, assay: str) -> dict:
        """
        Add blacklist data to variants.

        This method enriches a list of variants with blacklist data from the database.
        It checks if each variant's `simple_id` exists in the blacklist collection
        for the specified assay and adds the corresponding `in_normal_perc` value
        to the variant if found.

        Args:
            variants (list): A list of variant dictionaries, each containing a `simple_id` key.
            assay (str): The assay type used to filter blacklist data.

        Returns:
            list: The updated list of variants with blacklist data added where applicable.
        """
        short_pos = [var.get("simple_id") for var in variants]

        blacklisted = self.get_collection().find(
            {"assay": assay, "pos": {"$in": short_pos}},
            {"pos": 1, "in_normal_perc": 1, "_id": 0},
        )
        blacklisted_dict = {elem["pos"]: elem["in_normal_perc"] for elem in list(blacklisted)}

        for var in variants:
            if var["simple_id"] in blacklisted_dict:
                var["blacklist"] = blacklisted_dict[var["simple_id"]]

        return variants

    def blacklist_variant(self, var: dict, assay: str) -> OperationResult:
        """
        Add a variant to the blacklist collection.

        This method inserts a variant into the blacklist collection in the database.
        It uses the `simple_id` of the variant to identify it and associates it with
        the specified assay.

        Args:
            var (dict): A dictionary containing variant details. If `simple_id` is not
                        present, it will be generated using `CommonUtility.get_simple_id`.
            assay (str): The assay type to associate with the variant.

        Returns:
            OperationResult: JSON-safe mutation summary.
        """
        short_pos = var.get("simple_id", get_simple_id(var))

        return OperationResult.from_insert_one(
            self.get_collection().insert_one(
                {"assay": assay, "in_normal_perc": 1, "pos": short_pos}
            )
        )

    def get_blacklisted_count(self) -> int:
        """
        Get the count of blacklisted entries.
        This method retrieves all blacklist entries from the collection
        and returns their count.
        Returns:
            int: The count of blacklisted entries. Returns 0 if no entries are found.
        """
        return self.get_collection().count_documents({}) or 0

    def get_unique_blacklist_count(self) -> int:
        """
        Get the count of unique blacklist entries.

        This method aggregates the blacklist collection to count the number of unique
        blacklist entries based on the `pos` field.

        Returns:
            int: The count of unique blacklist entries. Returns 0 if no entries are found
                 or if an error occurs during the aggregation.
        """
        result = list(
            self.get_collection().aggregate(
                [
                    {"$group": {"_id": "$pos"}},
                    {"$count": "count"},
                ],
                allowDiskUse=True,
            )
        )
        if not result:
            return 0
        return int(result[0].get("count", 0) or 0)
