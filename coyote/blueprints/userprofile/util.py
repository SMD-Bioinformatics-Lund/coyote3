import re
from collections import defaultdict
from datetime import datetime

from flask import current_app as app
from werkzeug.security import generate_password_hash


class ProfileUtility:
    """
    Utility class for user profiles
    """

    @staticmethod
    def hash_password(password):
        """
        Hash a password
        """
        return generate_password_hash(
            password,
            method="pbkdf2:sha256",
        )

    @staticmethod
    def format_new_user_data(form_data):
        """
        Format new user data
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
