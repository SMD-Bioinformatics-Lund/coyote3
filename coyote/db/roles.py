from coyote.db.base import BaseHandler
from flask import current_app as app
from functools import lru_cache
from bson.objectid import ObjectId
from datetime import datetime
from flask_login import current_user


class RolesHandler(BaseHandler):
    """
    Coyote roles db actions
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.roles_collection)

    def get_all_roles(self) -> dict:
        """
        Get all roles
        """
        return list(self.get_collection().find({}).sort("level", -1))

    def save_role(self, role_data: dict) -> dict:
        """
        Save a role
        """
        self.get_collection().insert_one(role_data)

    def update_role(self, role_id: str, role_data: dict) -> dict:
        """
        Update a role
        """
        self.get_collection().update_one({"_id": role_id}, {"$set": role_data})
        return self.get_role(role_id)

    def get_role(self, role_id: str) -> dict:
        """
        Get a role
        """
        return self.get_collection().find_one({"_id": role_id.lower()})

    def delete_role(self, role_id: str) -> dict:
        """
        Delete a role
        """
        self.get_collection().delete_one({"_id": role_id})

    def toggle_active(self, role_id: str, active_status: bool) -> bool:
        """
        Toggles the active status of a role document by updating its 'is_active' field.
        """
        return self.get_collection().update_one(
            {"_id": role_id}, {"$set": {"is_active": active_status}}
        )
