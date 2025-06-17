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
Utility functions for user profile management, including password hashing and user data formatting.
"""

from datetime import datetime
from werkzeug.security import generate_password_hash


class ProfileUtility:
    """
    Utility class for user profile management.

    Provides static methods for:
    - Hashing user passwords securely.
    - Formatting new user data for storage, including hashing passwords and setting timestamps.
    """

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using PBKDF2 with SHA256.

        Args:
            password (str): The plain text password to hash.

        Returns:
            str: The securely hashed password.
        """
        return generate_password_hash(
            password,
            method="pbkdf2:sha256",
        )

    @staticmethod
    def format_new_user_data(form_data: dict) -> dict:
        """
        Format new user data for storage.

        Args:
            form_data (dict): Dictionary containing user input fields. Expected keys are:
                - "username": str, the user's unique identifier.
                - "email": str, the user's email address.
                - "fullname": str, the user's full name.
                - "groups": str, comma-separated group names.
                - "role": str, the user's role.
                - "password": str, the user's plain text password.

        Returns:
            dict: Formatted user data with hashed password and timestamps.
        """
        user_data = {
            "_id": form_data["username"],
            "email": form_data["email"],
            "fullname": form_data["fullname"],
            "groups": list(set(form_data["groups"].split(","))),
            "role": form_data["role"],
            "password": ProfileUtility.hash_password(form_data["password"]),
            "created": datetime.now(),
            "updated": datetime.now(),
        }

        return user_data
