

"""
RolesHandler module for Coyote3
===============================

This module defines the `RolesHandler` class used for accessing and managing
roles data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.infra.db.base import BaseHandler
from typing import Any


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class RolesHandler(BaseHandler):
    """
    RolesHandler is a class that provides an interface for interacting with the roles data in the MongoDB collection.

    This class extends the BaseHandler class and includes methods for performing CRUD operations, toggling role activity,
    and retrieving role-specific data. It is designed to manage role documents efficiently and ensure seamless integration
    with the database.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.roles_collection)

    def ensure_indexes(self) -> None:
        """
        Create minimal indexes for role list/count paths.
        """
        col = self.get_collection()
        col.create_index(
            [("role_id", 1)],
            name="role_id_1",
            unique=True,
            background=True,
            partialFilterExpression={"role_id": {"$exists": True, "$type": "string"}},
        )
        col.create_index([("level", -1)], name="level_-1", background=True)
        col.create_index([("is_active", 1)], name="is_active_1", background=True)

    @staticmethod
    def _normalize_role_id(role_id: str | None) -> str | None:
        if role_id is None:
            return None
        normalized = str(role_id).strip().lower()
        return normalized or None

    def _role_lookup_query(self, role_id: str) -> dict:
        normalized = self._normalize_role_id(role_id)
        return {"role_id": normalized}

    def ensure_role_id(self, role_data: dict) -> dict:
        if not isinstance(role_data, dict):
            return role_data
        normalized = self._normalize_role_id(role_data.get("role_id"))
        if normalized:
            role_data["role_id"] = normalized
            return role_data
        raise ValueError("roles.role_id is required in strict business-key mode")

    def count_roles(self, is_active: bool | None = None) -> int:
        """
        Count roles with an optional active-status filter.
        """
        query = {}
        if is_active is not None:
            query["is_active"] = is_active
        return int(self.get_collection().count_documents(query))

    def get_all_roles(self) -> list:
        """
        Retrieve all roles from the database.

        This method fetches all role documents from the roles collection and sorts them
        in descending order based on their `level` field.

        Returns:
            list: A list of role documents sorted by their `level` field in descending order.
        """
        return list(self.get_collection().find({}).sort("level", -1))

    def get_all_role_names(self) -> list:
        """
        Retrieve all active role names.

        This method fetches the names of all roles that are currently active in the database.

        Returns:
            list: A list of role names (IDs) for active roles.
        """
        return [
            role.get("role_id")
            for role in self.get_collection().find(
                {"is_active": True}, {"_id": 1, "role_id": 1}
            )
        ]

    def get_role_colors(self) -> list:
        """
        Retrieve all role colors.

        This method fetches the colors of all roles from the database.

        Returns:
            list: A list of role colors.
        """
        roles = self.get_collection().find({}, {"color": 1})
        roles_colors = {}
        for role in roles:
            role_key = role.get("role_id")
            roles_colors[role_key] = role["color"]
        return roles_colors

    def create_role(self, role_data: dict) -> Any:
        """
        Save a role.

        This method inserts a new role document into the roles collection.

        Args:
            role_data (dict): A dictionary containing the role details to be saved.

        Returns:
            Any
        """
        payload = self.ensure_role_id(dict(role_data))
        self.get_collection().insert_one(payload)

    def update_role(self, role_id: str, role_data: dict) -> dict:
        """
        Update a role.

        This method updates an existing role document in the roles collection.

        Args:
            role_id (str): The unique identifier of the role to update.
            role_data (dict): A dictionary containing the updated role details.

        Returns:
            dict: The updated role document.
        """
        payload = self.ensure_role_id(dict(role_data))
        self.get_collection().update_one(self._role_lookup_query(role_id), {"$set": payload})
        return self.get_role(role_id)

    def get_role(self, role_id: str) -> dict:
        """
        Retrieve a role document.

        This method fetches a single role document from the database based on its unique identifier.

        Args:
            role_id (str): The unique identifier of the role to retrieve.

        Returns:
            dict: The role document if found, otherwise None.
        """
        normalized = self._normalize_role_id(role_id)
        if not normalized:
            return None
        return self.get_collection().find_one({"role_id": normalized})

    def delete_role(self, role_id: str) -> Any:
        """
        Delete a role.

        This method removes a role document from the database based on its unique identifier.

        Args:
            role_id (str): The unique identifier of the role to delete.

        Returns:
            Any: The result of the delete operation.
        """
        self.get_collection().delete_one(self._role_lookup_query(role_id))

    def toggle_role_active(self, role_id: str, active_status: bool) -> Any:
        """
        Toggle the active status of a role.

        This method updates the `is_active` field of a role document to the specified active status.

        Args:
            role_id (str): The unique identifier of the role to update.
            active_status (bool): The desired active status to set for the role.

        Returns:
            Any: The result of the update operation.
        """
        return self.get_collection().update_one(
            self._role_lookup_query(role_id),
            {"$set": {"is_active": active_status}},
        )

    def get_all_roles_plus_permissions(self) -> list:
        """
        Retrieve all roles from the database.

        This method fetches all role documents from the roles collection and sorts them
        in descending order based on their `level` field.

        Returns:
            list: A list of role documents sorted by their `level` field in descending order.
        """
        return list(
            self.get_collection().find(
                {},
                {"_id": 1, "name": 1, "permissions": 1, "deny_permissions": 1},
            )
        )

    def get_role_permissions(self, role_id: str) -> dict:
        """
        Retrieve the permissions of a specific role.

        This method fetches the permissions and deny_permissions fields of a role document
        based on its unique identifier.

        Args:
            role_id (str): The unique identifier of the role to retrieve permissions for.

        Returns:
            dict: A dictionary containing the permissions and deny_permissions fields.
        """
        return self.get_collection().find_one(
            self._role_lookup_query(role_id), {"permissions": 1, "deny_permissions": 1}
        )
