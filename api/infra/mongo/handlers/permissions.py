"""
PermissionsHandler module for Coyote3
=====================================

This module defines the `PermissionsHandler` class used for accessing and managing
permissions data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import re
from typing import Any, List, Optional

from api.infra.mongo.handlers.base import BaseHandler


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

    def ensure_indexes(self) -> None:
        """Ensure indexes.

        Returns:
            None.
        """
        col = self.get_collection()
        col.create_index(
            [("permission_id", 1)],
            name="permission_id_1",
            unique=True,
            background=True,
            partialFilterExpression={"permission_id": {"$exists": True, "$type": "string"}},
        )
        col.create_index([("category", 1)], name="category_1", background=True)
        col.create_index([("is_active", 1)], name="is_active_1", background=True)
        col.create_index(
            [("category", 1), ("is_active", 1)],
            name="category_1_is_active_1",
            background=True,
        )

    @staticmethod
    def _normalize_permission_id(permission_id: str | None) -> str | None:
        """Normalize permission id.

        Args:
                permission_id: Permission id.

        Returns:
                The  normalize permission id result.
        """
        normalized = str(permission_id or "").strip().lower()
        return normalized or None

    def _permission_lookup_query(self, permission_id: str) -> dict:
        """Permission lookup query.

        Args:
                permission_id: Permission id.

        Returns:
                The  permission lookup query result.
        """
        normalized = self._normalize_permission_id(permission_id)
        if not normalized:
            return {"permission_id": None}
        return {"permission_id": normalized}

    def ensure_permission_id(self, policy: dict) -> dict:
        """Ensure a permission payload carries a normalized business key."""
        if not isinstance(policy, dict):
            return policy
        normalized = self._normalize_permission_id(policy.get("permission_id"))
        if normalized:
            policy["permission_id"] = normalized
            return policy
        raise ValueError("permissions.permission_id is required in strict business-key mode")

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
        query = (
            {"$or": [{"is_active": True}, {"is_active": {"$exists": False}}]} if is_active else {}
        )
        return list(self.get_collection().find(query).sort("category"))

    def search_permissions(
        self, *, q: str = "", page: int = 1, per_page: int = 30, is_active: bool = False
    ) -> tuple[list[dict], int]:
        """Search permission policies directly in MongoDB and return paged results."""
        query: dict = (
            {"$or": [{"is_active": True}, {"is_active": {"$exists": False}}]} if is_active else {}
        )
        normalized_q = str(q or "").strip()
        if normalized_q:
            pattern = re.escape(normalized_q)
            query["$and"] = [
                {
                    "$or": [
                        {"permission_id": {"$regex": pattern, "$options": "i"}},
                        {"label": {"$regex": pattern, "$options": "i"}},
                        {"category": {"$regex": pattern, "$options": "i"}},
                        {"description": {"$regex": pattern, "$options": "i"}},
                    ]
                }
            ]
        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 30), 200))
        skip = (page - 1) * per_page
        col = self.get_collection()
        total = int(col.count_documents(query))
        docs = list(
            col.find(query).sort([("category", 1), ("permission_id", 1)]).skip(skip).limit(per_page)
        )
        return docs, total

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
                {
                    "category": category,
                    "$or": [{"is_active": True}, {"is_active": {"$exists": False}}],
                }
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
        permission_query = self._normalize_permission_id(permission)
        return (
            self.get_collection().find_one(
                {
                    "$and": [
                        {"permission_id": permission_query},
                        {"$or": [{"is_active": True}, {"is_active": {"$exists": False}}]},
                    ]
                }
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
        return self.get_collection().find_one(self._permission_lookup_query(permission_id))

    def create_new_policy(self, policy: dict) -> Any:
        """
        Insert a single permission policy into the collection.

        This method inserts a single permission document into the permissions collection.

        Args:
            policy (dict): A dictionary containing the details of the permission policy to insert.

        Returns:
            Any: The result of the insert operation.
        """
        self.get_collection().insert_one(self.ensure_permission_id(dict(policy)))

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
            self._permission_lookup_query(permission_id), {"$set": data}
        )

    def toggle_policy_active(self, permission_id: str, active_status: bool) -> Any:
        """
        Toggle the active status of a permission.

        This method updates the `is_active` field of a permission document to the specified active status.

        Args:
            permission_id (str): The unique identifier of the permission to update.
            active_status (bool): The desired active status to set for the permission.

        Returns:
            Any: The result of the update operation.
        """
        return self.get_collection().update_one(
            self._permission_lookup_query(permission_id),
            {"$set": {"is_active": active_status}},
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
        return self.get_collection().delete_one(self._permission_lookup_query(permission_id))
