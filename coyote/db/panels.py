# -*- coding: utf-8 -*-
"""
PanelsHandler module for Coyote3
================================

This module defines the `PanelsHandler` class used for accessing and managing
gene panel data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler
from typing import Any


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class PanelsHandler(BaseHandler):
    """
    Coyote gene panels database handler.

    The `PanelsHandler` class provides a comprehensive interface for managing
    gene panel data stored in a MongoDB database. It extends the functionality
    of the `BaseHandler` class and is designed to be used in a Flask application.

    This class includes methods for performing CRUD (Create, Read, Update, Delete)
    operations on gene panel data, as well as advanced queries and calculations
    such as retrieving unique gene counts, toggling panel statuses, and fetching
    distinct panel groups or assay names.

    It is a core component of the `coyote.db` package, facilitating efficient
    and organized access to gene panel information.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.panels_collection)

    def get_panel(self, panel_name: str) -> list:
        """
        Retrieve a panel by its name or ID.

        This method queries the database collection to find a single document
        that matches the provided `panel_name` or `panel_id`.

        Args:
            panel_name (str): The unique name or identifier of the panel to retrieve.

        Returns:
            list: A dictionary representing the panel document, or None if no
            document is found.
        """
        return self.get_collection().find_one({"_id": panel_name})

    def get_all_panels(self) -> list:
        """
        Fetch all panels.

        This method retrieves all documents from the database collection
        representing panels, excluding the `genes` field. The results are
        sorted in descending order based on the `created_on` field.

        Returns:
            list: A list of all panel documents from the database.
        """
        return list(
            self.get_collection()
            .find({}, {"genes": 0})
            .sort([("created_on", -1)])
        )

    def get_all_assay_panels(self) -> list:
        """
        Fetch all panels and calculate covered_genes_count properly.

        This method retrieves all documents from the database collection
        representing assay panels. The `covered_genes_count` is calculated
        as part of the process.

        Returns:
            list: A list of all assay panel documents from the database.
        """
        return list(self.get_collection().find())

    def insert_panel(self, data: dict) -> Any:
        """
        Insert a gene panel into the database.

        This method adds a new gene panel document to the database collection.

        Args:
            data (dict): A dictionary containing the gene panel data to be inserted.

        Returns:
            Any: The result of the insert operation, typically an instance of
            `pymongo.results.InsertOneResult` that includes the ID of the inserted document.
        """
        return self.get_collection().insert_one(data)

    def update_panel(self, assay_panel_id, panel_data) -> None:
        """
        Update a panel's data in the database.
        Args:
            assay_panel_id: The unique identifier of the panel.
            panel_data: The new data to replace the existing panel data.
        Returns:
            None
        """
        return self.get_collection().replace_one(
            {"_id": assay_panel_id}, panel_data
        )

    def toggle_active(self, panel_id: str, active_status: bool) -> bool:
        """
        Toggles the active status of a panel in the database.
        Args:
            panel_id (str): The unique identifier of the panel.
            active_status (bool): The desired active status to set.
        Returns:
            bool: True if the update was successful, False otherwise.
        """
        return self.get_collection().update_one(
            {"_id": panel_id}, {"$set": {"is_active": active_status}}
        )

    def delete_panel(self, panel_id: str) -> None:
        """
        Delete a panel from the database by its unique ID.

        This method removes a single document from the database collection
        that matches the provided `panel_id`.

        Args:
            panel_id (str): The unique identifier of the panel to be deleted.

        Returns:
            None
        """
        self.get_collection().delete_one({"_id": panel_id})

    def get_unique_all_panel_gene_count(self) -> int:
        """
        Calculate the total number of unique genes across all panels.

        This method queries the database collection to retrieve the `covered_genes` field
        for all documents. It then aggregates all the genes into a set to ensure uniqueness
        and calculates the total count of unique genes.

        Returns:
            int: The total count of unique genes across all panels.
        """
        docs = self.get_collection().find({}, {"covered_genes": 1})
        all_genes = {gene for doc in docs for gene in doc["covered_genes"]}
        return len(all_genes)

    def get_assay_gene_counts(self) -> dict:
        """
        Get a dictionary where assays are keys and counts of genes are values.

        This method queries the database collection to retrieve information about
        assays, including the number of genes covered, display names, and panel groups.
        It processes the data into a dictionary where each assay name (`panel_name`)
        is a key, and the value is another dictionary containing:
            - `gene_count`: The number of genes covered by the assay.
            - `display_name`: The display name of the assay.
            - `panel_group`: The group to which the assay belongs.

        Returns:
            dict: A dictionary mapping assay names to their respective gene counts
                and metadata.
        """
        docs = self.get_collection().find(
            {},
            {
                "covered_genes": 1,
                "panel_name": 1,
                "display_name": 1,
                "panel_group": 1,
            },
        )
        result = {
            doc["panel_name"]: {
                "gene_count": len(doc["covered_genes"]),
                "display_name": doc["display_name"],
                "panel_group": doc["panel_group"],
            }
            for doc in docs
        }
        return result

    def get_all_groups(self) -> list:
        """
        Fetch distinct panel groups across all gene panels.

        This method queries the database collection to retrieve a list of unique
        values for the `panel_group` field, which represents the grouping of panels.

        Returns:
            list: A list of unique panel group names.
        """
        return self.get_collection().distinct("panel_group")

    def get_all_assays(self) -> list:
        """
        Fetch distinct assay names across all panels.

        Returns:
            list: A list of unique assay names (`panel_name`) from the database.
        """
        return self.get_collection().distinct("panel_name")

    def get_panel_genes(self, panel_id: str) -> list:
        """
        Retrieve the genes associated with a specific panel.

        This method queries the database collection to find a single document
        that matches the provided `panel_id`. It then extracts and returns the
        `covered_genes` field from the document.

        Args:
            panel_id (str): The unique identifier of the panel whose genes are to be retrieved.

        Returns:
            list: A list of genes associated with the specified panel.
        """
        doc = self.get_collection().find_one({"_id": panel_id})
        if not doc:
            return []
        return doc.get("covered_genes", [])
