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
ASPHandler module for Coyote3
================================

This module defines the `ASPHandler` class used for accessing and managing
assay specific panel data in MongoDB.

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
class ASPHandler(BaseHandler):
    """
    Coyote assay specific asp database handler.

    The `ASPHandler` class provides a comprehensive interface for managing
    assay specific panel data stored in a MongoDB database. It extends the functionality
    of the `BaseHandler` class and is designed to be used in a Flask application.

    This class includes methods for performing CRUD (Create, Read, Update, Delete)
    operations on gene panel data, as well as advanced queries and calculations
    such as retrieving unique gene counts, toggling panel statuses, and fetching
    distinct panel groups or assay names.

    It is a core component of the `coyote.db` package, facilitating efficient
    and organized access to assay specific panel information.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.asp_collection)

    def get_asp(self, asp_name: str) -> dict | None:
        """
        Retrieve an assay specific panel (ASP) by its name or ID.

        This method queries the database collection to find a single document
        that matches the provided `asp_name` or `asp_id`.

        Args:
            asp_name (str): The unique name or identifier of the panel to retrieve.

        Returns:
            dict: A dictionary representing the panel document, or None if no
            document is found.
        """
        return self.get_collection().find_one({"_id": asp_name})

    def get_all_asps(self, is_active: bool | None = None) -> list:
        """
        Retrieve all assay specific asp (ASPs), optionally filtered by active status.

        This method fetches all panel documents from the database collection,
        excluding the `covered_genes` and `version_history` fields for efficiency.
        If `is_active` is specified, only asps matching the active status are returned.
        The results are sorted in descending order by the `created_on` field.

        Args:
            is_active (bool | None): If provided, filters asp by their active status.

        Returns:
            list: A list of panel documents from the database.
        """
        query = {}
        if is_active is not None:
            query["is_active"] = is_active

        cursor = (
            self.get_collection()
            .find(query, {"covered_genes": 0, "version_history": 0})
            .sort("created_on", -1)
        )
        return list(cursor)

    def create_asp(self, data: dict) -> Any:
        """
        Insert a assay specific panel into the database.

        This method adds a new assay specific panel document to the database collection.

        Args:
            data (dict): A dictionary containing the asp data to be inserted.

        Returns:
            Any: The result of the insert operation, typically an instance of
            `pymongo.results.InsertOneResult` that includes the ID of the inserted document.
        """
        return self.get_collection().insert_one(data)

    def update_asp(self, asp_id, asp_data) -> None:
        """
        Update a panel's data in the database.
        Args:
            asp_id: The unique identifier of the panel.
            asp_data: The new data to replace the existing panel data.
        Returns:
            None
        """
        return self.get_collection().replace_one({"_id": asp_id}, asp_data)

    def toggle_asp_active(self, asp_id: str, active_status: bool) -> bool:
        """
        Toggle the active status of an assay specific panel (ASP) in the database.

        This method updates the `is_active` field of a specific ASP document
        identified by `asp_id`.

        Args:
            asp_id (str): The unique identifier of the ASP.
            active_status (bool): The desired active status to set.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        return self.toggle_active(asp_id, active_status)

    def delete_asp(self, asp_id: str) -> None:
        """
        Delete a panel from the database by its unique ID.

        This method removes a single document from the database collection
        that matches the provided `panel_id`.

        Args:
            asp_id (str): The unique identifier of the panel to be deleted.

        Returns:
            None
        """
        self.get_collection().delete_one({"_id": asp_id})

    def get_all_asps_unique_gene_count(self) -> int:
        """
        Calculate the total number of unique genes across all asp.

        This method queries the database collection to retrieve the `covered_genes` field
        for all documents. It then aggregates all the genes into a set to ensure uniqueness
        and calculates the total count of unique genes.

        Returns:
            int: The total count of unique genes across all asp.
        """
        docs = self.get_collection().find({}, {"covered_genes": 1})
        all_genes = set()
        for doc in docs:
            genes = doc.get("covered_genes", [])
            all_genes.update(genes)
        return len(all_genes)

    def get_all_asp_gene_counts(self) -> dict:
        """
        Get a dictionary mapping assay panel names to gene counts and metadata.

        This method queries the database collection to retrieve information about
        each assay panel, including the number of genes covered (`covered_genes`),
        the display name (`display_name`), and the panel group (`asp_group`).
        It returns a dictionary where each key is a panel name (`panel_name`),
        and the value is another dictionary containing:
            - `gene_count`: The number of genes covered by the panel.
            - `display_name`: The display name of the panel.
            - `asp_group`: The group to which the panel belongs.

        Returns:
            dict: A dictionary mapping panel names to their gene counts and metadata.
        """
        docs = self.get_collection().find(
            {},
            {
                "covered_genes_count": 1,
                "germline_genes_count": 1,
                "assay_name": 1,
                "display_name": 1,
                "asp_group": 1,
                "accredited": 1,
            },
        )

        return docs

    def get_all_asp_groups(self) -> list:
        """
        Fetch distinct groups across all assay specific asp.

        This method queries the database collection to retrieve a list of unique
        values for the `asp_group` field, which represents the grouping of asp.

        Returns:
            list: A list of unique panel group names.
        """
        return self.get_collection().distinct("asp_group")

    def get_all_assays(self, is_active: bool | None = None) -> list:
        """
        Fetch distinct assay names across all assay specific asp.

        Returns:
            list: A list of unique assay names (`assay_name`) from the database.
        """
        if is_active is None:
            return self.get_collection().distinct("assay_name")
        else:
            return (
                self.get_collection()
                .find({"is_active": is_active})
                .distinct("assay_name")
            )

    def get_asp_genes(self, asp_id: str) -> tuple:
        """
        Retrieve the genes associated with a specific panel.

        This method queries the database collection to find a single document
        that matches the provided `asp_id`. It then extracts and returns a tuple
        containing the `covered_genes` and `germline_genes` fields from the document.

        Args:
            asp_id (str): The unique identifier of the panel whose genes are to be retrieved.

        Returns:
            tuple: A tuple containing two lists:
                - The first list contains genes in the `covered_genes` field.
                - The second list contains genes in the `germline_genes` field.
            If the panel is not found, both lists are empty.
        """
        doc = self.get_collection().find_one({"_id": asp_id})
        if not doc:
            return [], []
        return doc.get("covered_genes", []), doc.get("germline_genes", [])

    def get_asp_group_mappings(self) -> dict:
        """
        Retrieves a dictionary mapping assay IDs to their respective assay groups.

        This method queries the collection to fetch all documents, extracting the `_id`
        and `asp_group` fields. It then constructs a dictionary where the keys are
        assay IDs (`_id`) and the values are their corresponding assay groups.

        Returns:
            dict: A dictionary mapping assay IDs to assay groups.
        """
        result = self.get_collection().find({}, {"_id": 1, "asp_group": 1})

        mappings = {}
        if result:
            for assay in result:
                if assay["_id"] not in mappings:
                    mappings[assay["_id"]] = assay["asp_group"]

        return mappings
