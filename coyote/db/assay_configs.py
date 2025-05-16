# -*- coding: utf-8 -*-
"""
AssayConfigsHandler module for Coyote3
======================================

This module defines the `AssayConfigsHandler` class used for accessing and managing
assay configuration data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler
from typing import Any
from pymongo import cursor


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class AssayConfigsHandler(BaseHandler):
    """
    AssayConfigsHandler is a class responsible for managing assay configuration data
    stored in a MongoDB collection. It provides methods to perform CRUD operations
    on assay configurations, retrieve specific data, toggle the active status of an
    assay configuration, and manage assay groups and mappings. This class serves as
    a key component for handling assay-related data efficiently in the database.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.assay_configs_collection)

    def get_all_assay_configs(self) -> cursor.Cursor:
        """
        Retrieves all assay configuration documents from the collection.

        Returns:
            pymongo.cursor.Cursor: A cursor to iterate over all assay configuration documents.
        """
        return self.get_collection().find({})

    def get_assay_config(self, assay_id: str) -> dict | None:
        """
        Retrieves a specific assay configuration document by its ID.

        Args:
            assay_id (str): The unique identifier of the assay configuration.

        Returns:
            dict | None: The assay configuration document if found, otherwise None.
        """
        return self.get_collection().find_one({"_id": assay_id})

    def get_assay_config_filtered(self, assay_id: str) -> dict | None:
        """
        Retrieves a specific assay configuration document by its ID, ensuring it is active.

        This method filters the assay configuration document by its unique identifier (`_id`)
        and checks that the `is_active` field is set to `True`. Additionally, it excludes
        metadata fields such as `updated_on`, `updated_by`, `created_on`, and `created_by`
        from the result.

        Args:
            assay_id (str): The unique identifier of the assay configuration.

        Returns:
            dict: The filtered assay configuration document if found, otherwise `None`.
        """
        return self.get_collection().find_one(
            {"_id": assay_id, "is_active": True},
            {
                "updated_on": 0,
                "updated_by": 0,
                "created_on": 0,
                "created_by": 0,
            },
        )

    def update_assay_config(self, assay_id: str, data: dict) -> Any:
        """
        Updates an existing assay configuration document with new data.

        Args:
            assay_id (str): The unique identifier of the assay configuration to update.
            data (dict): A dictionary containing the fields to update and their new values.

        Returns:
            Any: The result of the update operation, typically a `pymongo.results.UpdateResult` object.
        """
        return self.get_collection().update_one(
            {"_id": assay_id}, {"$set": data}
        )

    def insert_assay_config(self, data: dict) -> Any:
        """
        Inserts a new assay configuration document into the collection.

        Args:
            data (dict): A dictionary containing the assay configuration fields and their values.

        Returns:
            Any: The result of the insert operation, typically a `pymongo.results.InsertOneResult` object.
        """
        return self.get_collection().insert_one(data)

    def delete_assay_config(self, assay_id: str) -> Any:
        """
        Deletes an assay configuration document by its ID.

        Args:
            assay_id (str): The unique identifier of the assay configuration to delete.

        Returns:
            Any: The result of the delete operation, typically a `pymongo.results.DeleteResult` object.
        """
        return self.get_collection().delete_one({"_id": assay_id})

    def toggle_active(self, assay_id: str, active_status: bool) -> bool:
        """
        Toggles the active status of an assay configuration document by updating its 'is_active' field.

        Args:
            assay_id (str): The unique identifier of the assay configuration to update.
            active_status (bool): The desired active status to set for the assay configuration.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        return self.get_collection().update_one(
            {"_id": assay_id}, {"$set": {"is_active": active_status}}
        )

    def get_all_assay_groups(self) -> dict:
        """
        Retrieves a distinct list of all assay groups from the collection.

        Returns:
            dict: A dictionary containing all unique assay groups.
        """
        return self.get_collection().distinct("assay_group")

    def get_all_assay_names(self) -> dict:
        """
        Retrieves a distinct list of all assay names from the collection.

        Returns:
            dict: A dictionary containing all unique assay names.
        """
        return self.get_collection().distinct("assay_name")

    def get_assay_group_mappings(self) -> dict:
        """
        Retrieves a dictionary mapping assay IDs to their respective assay groups.

        This method queries the collection to fetch all documents, extracting the `_id`
        and `assay_group` fields. It then constructs a dictionary where the keys are
        assay IDs (`_id`) and the values are their corresponding assay groups.

        Returns:
            dict: A dictionary mapping assay IDs to assay groups.
        """
        result = self.get_collection().find({}, {"_id": 1, "assay_group": 1})

        mappings = {}
        if result:
            for assay in result:
                if assay["_id"] not in mappings:
                    mappings[assay["_id"]] = assay["assay_group"]

        return mappings

    def get_assay_available_envs(
        self, assay_name: str, all_envs: list
    ) -> list:
        """
        Retrieves a list of available environments for a specific assay configuration.

        Args:
            assay_name (str): The base assay name (e.g., "Demo").
            all_envs (list): All supported environments (e.g., ["production", "development", "validation"]).

        Returns:
            list: A list of environments not yet used for this assay.
        """
        # Match _id like "Demo:production", "Demo:development", etc.
        regex = f"^{assay_name}:"
        assay_configs = self.get_collection().find(
            {"_id": {"$regex": regex}}, {"_id": 1}
        )

        used_envs = set()
        for config in assay_configs:
            try:
                _, env = config["_id"].split(":")
                used_envs.add(env)
            except ValueError:
                continue  # skip malformed _id

        return [env for env in all_envs if env not in used_envs]
