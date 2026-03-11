
"""
UsersHandler module for Coyote3
===============================

This module defines the `UsersHandler` class used for accessing and managing
user data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.infra.db.base import BaseHandler
from datetime import datetime
from api.runtime import flash


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class UsersHandler(BaseHandler):
    """
    The UsersHandler class provides methods to manage user data in the database.

    This class includes functionality for retrieving, creating, updating, and deleting user records,
    as well as managing user-specific attributes such as passwords, active status, and last login timestamps.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.users_collection)

    def ensure_indexes(self) -> None:
        """
        Create minimal indexes for hot user lookup/count paths.

        Kept intentionally small to avoid unnecessary disk growth.
        """
        col = self.get_collection()
        col.create_index(
            [("user_id", 1)],
            name="user_id_1",
            unique=True,
            background=True,
            partialFilterExpression={"user_id": {"$exists": True, "$type": "string"}},
        )
        col.create_index([("email", 1)], name="email_1", background=True)
        col.create_index([("is_active", 1)], name="is_active_1", background=True)
        col.create_index([("firstname", 1)], name="firstname_1", background=True)

    def count_users(self, is_active: bool | None = None) -> int:
        """
        Count users with an optional active-status filter.
        """
        query = {}
        if is_active is not None:
            query["is_active"] = is_active
        return int(self.get_collection().count_documents(query))

    @staticmethod
    def _normalize_user_id(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    def user(self, user_mail: str) -> dict:
        """
        Retrieves a user document from the database by email.
        Args:
            user_mail (str): The email address of the user.
        Returns:
            dict: A dictionary representation of the user document.
        """
        normalized = self._normalize_user_id(user_mail)
        if not normalized:
            return None
        col = self.get_collection()
        return (
            col.find_one({"email": normalized})
            or col.find_one({"username": normalized})
            or col.find_one({"user_id": normalized})
            or col.find_one({"_id": normalized})
        )

    def user_with_id(self, user_id: str) -> dict | None:
        """
        Retrieve a user document from the database by user ID.
        Args:
            user_id (str): The unique identifier of the user.
        Returns:
            dict | None: A dictionary representation of the user document, or None when missing.
        """
        normalized = self._normalize_user_id(user_id)
        if not normalized:
            return None
        doc = self.get_collection().find_one({"user_id": normalized}) or self.get_collection().find_one(
            {"_id": normalized}
        )
        return dict(doc) if doc else None

    def ensure_user_id(self, user_data: dict) -> dict:
        """
        Ensure user payload contains explicit business key (`user_id`).
        """
        if not isinstance(user_data, dict):
            return user_data
        if self._normalize_user_id(user_data.get("user_id")):
            return user_data
        for candidate in (user_data.get("_id"), user_data.get("username"), user_data.get("email")):
            normalized = self._normalize_user_id(candidate)
            if normalized:
                user_data["user_id"] = normalized
                return user_data
        return user_data

    def update_password(self, username, password_hash) -> None:
        """
        Updates the password for a given username in the database.
        Args:
            username (str): The username of the user whose password is to be updated.
            password_hash (str): The new hashed password to set.
        Returns:
            None
        """
        normalized = self._normalize_user_id(username)
        if self.get_collection().update_one(
            {"$or": [{"user_id": normalized}, {"_id": normalized}]},
            {"$set": {"password": password_hash}},
        ):
            flash("Password updated", "green")
        else:
            flash("Failed to update password", "red")

    def user_exists(self, user_id=None, email=None) -> bool:
        """
        Check if a user exists in the database by user ID or email.
        Args:
            user_id (str, optional): The unique identifier of the user.
            email (str, optional): The email address of the user.
        Returns:
            bool: True if the user exists in the database, False otherwise.
        """
        if email:
            return bool(self.get_collection().find_one({"email": email}))

        if user_id:
            normalized = self._normalize_user_id(user_id)
            return bool(
                self.get_collection().find_one({"$or": [{"user_id": normalized}, {"_id": normalized}]})
            )

        return False

    def create_user(self, user_data: dict) -> None:
        """
        Inserts a new user document into the database.
        Args:
            user_data (dict): A dictionary containing user information to be stored.
        Returns:
            None
        """
        payload = self.ensure_user_id(dict(user_data))
        return self.get_collection().insert_one(payload)

    def get_all_users(self) -> list:
        """
        Retrieve all users from the database, sorted by fullname in ascending order.
        Returns:
            list: A list of user documents.
        """
        return list(self.get_collection().find().sort("firstname", 1))

    def delete_user(self, user_id) -> None:
        """
        Deletes a user from the database by their unique ID.
        Args:
            user_id: The unique identifier of the user to be deleted.
        Returns:
            None
        """
        normalized = self._normalize_user_id(user_id)
        return self.get_collection().delete_one({"$or": [{"user_id": normalized}, {"_id": normalized}]})

    def update_user(self, user_id, user_data) -> None:
        """
        Updates a user's data in the database.
        Args:
            user_id: The unique identifier of the user.
            user_data: The new data to replace the existing user data.
        Returns:
            None
        """
        normalized = self._normalize_user_id(user_id)
        payload = self.ensure_user_id(dict(user_data))
        return self.get_collection().replace_one(
            {"$or": [{"user_id": normalized}, {"_id": normalized}]}, payload
        )

    def update_user_last_login(self, user_id: str):
        """
        Updates the last login timestamp for a user in the database.

        Args:
            user_id (str): The unique identifier of the user.
        """
        normalized = self._normalize_user_id(user_id)
        self.get_collection().update_one(
            {"$or": [{"user_id": normalized}, {"_id": normalized}]},
            {"$set": {"last_login": datetime.utcnow()}},
        )

    def toggle_user_active(self, user_id: str, active_status: bool) -> bool:
        """
        Toggles the active status of a user in the database.
        Args:
            user_id (str): The unique identifier of the user.
            active_status (bool): The desired active status to set.
        Returns:
            bool: True if the update was successful, False otherwise.
        """
        normalized = self._normalize_user_id(user_id)
        result = self.get_collection().update_one(
            {"$or": [{"user_id": normalized}, {"_id": normalized}]},
            {"$set": {"is_active": active_status}},
        )
        return bool(getattr(result, "modified_count", 0) or getattr(result, "matched_count", 0))
