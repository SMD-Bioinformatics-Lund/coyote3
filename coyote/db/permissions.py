# -*- coding: utf-8 -*-
"""
PermissionsHandler module for Coyote3
=====================================

This module defines the `PermissionsHandler` class used for accessing and managing
permissions data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler
from typing import List, Optional, Any


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class PermissionsHandler(BaseHandler):
    """
    PermissionsHandler is a class that provides an interface for interacting with the permissions data in the MongoDB collection.

    This class extends the BaseHandler class and includes methods for performing CRUD operations, toggling active status,
    retrieving permissions by category, and validating permissions. It is designed to manage permission documents efficiently
    and ensure seamless integration with the database.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.permissions_collection)

    def get_all_permissions(self, is_active=True) -> List[dict]:
        """
        Retrieve all permissions.

        This method fetches all permission documents from the permissions collection.
        If `is_active` is True, only active permissions are retrieved; otherwise, all permissions are fetched.

        Args:
            is_active (bool): A flag to filter active permissions. Defaults to True.

        Returns:
            List[dict]: A list of permission documents sorted by their `category` field.
        """
        query = {"is_active": True} if is_active else {}
        return list(self.get_collection().find(query).sort("category"))

    def get_categories(self) -> List[str]:
        """
        Retrieve all unique permission categories.

        This method fetches all distinct values of the `category` field from the permissions collection
        and returns them as a sorted list.

        Returns:
            List[str]: A sorted list of unique permission categories.
        """
        return sorted(list(self.get_collection().distinct("category")))

    def get_by_category(self, category: str) -> List[dict]:
        """
        Retrieve permissions by category.

        This method fetches all active permission documents that belong to the specified category.

        Args:
            category (str): The category of permissions to retrieve.

        Returns:
            List[dict]: A list of active permission documents in the specified category.
        """
        return list(
            self.get_collection().find(
                {"category": category, "is_active": True}
            )
        )

    def is_valid(self, permission: str) -> bool:
        """
        Check if a permission is valid.

        This method verifies whether a given permission is active in the database.

        Args:
            permission (str): The unique identifier of the permission to validate.

        Returns:
            bool: True if the permission is active, False otherwise.
        """
        return (
            self.get_collection().find_one(
                {"_id": permission, "is_active": True}
            )
            is not None
        )

    def get_permission(self, permission_id: str) -> Optional[dict]:
        """
        Retrieve a permission document.

        This method fetches a single permission document from the database based on its unique identifier.

        Args:
        permission_id (str): The unique identifier of the permission to retrieve.

        Returns:
        Optional[dict]: The permission document if found, otherwise None.
        """
        return self.get_collection().find_one({"_id": permission_id})

    def create_new_policy(self, policy: dict) -> Any:
        """
        Insert a single permission policy into the collection.

        This method inserts a single permission document into the permissions collection.

        Args:
            policy (dict): A dictionary containing the details of the permission policy to insert.

        Returns:
            Any: The result of the insert operation.
        """
        self.get_collection().insert_one(policy)

    def update_policy(self, permission_id: str, data: dict) -> Any:
        """
        Update a permission policy.

        This method updates an existing permission document in the permissions collection.

        Args:
            permission_id (str): The unique identifier of the permission to update.
            data (dict): A dictionary containing the updated permission details.

        Returns:
            Any: The result of the update operation.
        """
        return self.get_collection().update_one(
            {"_id": permission_id}, {"$set": data}
        )

    def toggle_policy_active(
        self, permission_id: str, active_status: bool
    ) -> Any:
        """
        Toggle the active status of a permission.

        This method updates the `is_active` field of a permission document to the specified active status.

        Args:
            permission_id (str): The unique identifier of the permission to update.
            active_status (bool): The desired active status to set for the permission.

        Returns:
            Any: The result of the update operation.
        """
        return self.toggle_active(
            permission_id,
            active_status,
        )

    def delete_policy(self, permission_id: str) -> Any:
        """
        Delete a permission document.

        This method removes a permission document from the permissions collection based on its unique identifier.

        Args:
            permission_id (str): The unique identifier of the permission to delete.

        Returns:
            Any: The result of the delete operation.
        """
        return self.get_collection().delete_one({"_id": permission_id})
