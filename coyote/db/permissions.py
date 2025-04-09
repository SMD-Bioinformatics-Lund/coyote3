from coyote.db.base import BaseHandler
from flask import current_app as app
from functools import lru_cache
from bson.objectid import ObjectId
from datetime import datetime
from flask_login import current_user
from typing import List, Optional


class PermissionsHandler(BaseHandler):
    """
    Coyote permissions db actions
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.permissions_collection)

    def get_all(self, is_active=True) -> List[dict]:
        query = {"is_active": True} if is_active else {}
        return list(self.get_collection().find(query).sort("category"))

    def get_categories(self) -> List[str]:
        return sorted(list(self.get_collection().distinct("category")))

    def get_by_category(self, category: str) -> List[dict]:
        return list(self.get_collection().find({"category": category, "is_active": True}))

    def is_valid(self, permission: str) -> bool:
        return self.get_collection().find_one({"_id": permission, "is_active": True}) is not None

    def get(self, perm_id: str) -> Optional[dict]:
        return self.get_collection().find_one({"_id": perm_id})

    def insert_many(self, policies: List[dict]):
        self.get_collection().insert_many(policies, ordered=False)

    def insert_permission(self, policy: dict):
        """
        Insert a single policy into the collection.
        """
        self.get_collection().insert_one(policy)

    def update_policy(self, perm_id: str, data: dict):
        return self.get_collection().update_one({"_id": perm_id}, {"$set": data})

    def toggle_active(self, perm_id: str, active_status: bool) -> bool:
        """
        Toggles the active status of a permission document by updating its 'is_active' field.
        """
        return self.get_collection().update_one(
            {"_id": perm_id}, {"$set": {"is_active": active_status}}
        )

    def delete_permission(self, perm_id: str):
        """
        Deletes a permission document from the collection by its unique identifier.
        """
        return self.get_collection().delete_one({"_id": perm_id})
