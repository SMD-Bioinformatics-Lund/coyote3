# -*- coding: utf-8 -*-
"""
UsersHandler module for Coyote3
===============================

This module defines the `UsersHandler` class used for accessing and managing
user data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler
from datetime import datetime
from flask import flash


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

    def user(self, user_mail: str) -> dict:
        """
        Retrieves a user document from the database by email.
        Args:
            user_mail (str): The email address of the user.
        Returns:
            dict: A dictionary representation of the user document.
        """

        return self.get_collection().find_one({"email": user_mail})

    def user_with_id(self, user_id: str) -> dict:
        """
        Retrieve a user document from the database by user ID.
        Args:
            user_id (str): The unique identifier of the user.
        Returns:
            dict: A dictionary representation of the user document.
        """
        return dict(self.get_collection().find_one({"_id": user_id}))

    def update_password(self, username, password_hash) -> None:
        """
        Updates the password for a given username in the database.
        Args:
            username (str): The username of the user whose password is to be updated.
            password_hash (str): The new hashed password to set.
        Returns:
            None
        """
        if self.get_collection().update_one(
            {"_id": username}, {"$set": {"password": password_hash}}
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
            return bool(self.get_collection().find_one({"_id": user_id}))

        return False

    def create_user(self, user_data: dict) -> None:
        """
        Inserts a new user document into the database.
        Args:
            user_data (dict): A dictionary containing user information to be stored.
        Returns:
            None
        """
        return self.get_collection().insert_one(user_data)

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
        return self.get_collection().delete_one({"_id": user_id})

    def update_user(self, user_id, user_data) -> None:
        """
        Updates a user's data in the database.
        Args:
            user_id: The unique identifier of the user.
            user_data: The new data to replace the existing user data.
        Returns:
            None
        """
        return self.get_collection().replace_one({"_id": user_id}, user_data)

    def update_user_last_login(self, user_id: str):
        """
        Updates the last login timestamp for a user in the database.

        Args:
            user_id (str): The unique identifier of the user.
        """
        self.get_collection().update_one(
            {"_id": user_id}, {"$set": {"last_login": datetime.utcnow()}}
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
        return self.toggle_active(user_id, active_status)
