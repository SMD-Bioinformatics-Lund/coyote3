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
import re
from datetime import datetime, timezone

from api.infra.dashboard_cache import invalidate_dashboard_summary_cache
from api.infra.db.base import BaseHandler
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
            [("username", 1)],
            name="username_1",
            unique=True,
            background=True,
            partialFilterExpression={"username": {"$exists": True, "$type": "string"}},
        )
        col.create_index(
            [("email", 1)],
            name="email_1",
            unique=True,
            background=True,
            partialFilterExpression={"email": {"$exists": True, "$type": "string"}},
        )
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
        """Normalize user id.

        Args:
                value: Value.

        Returns:
                The  normalize user id result.
        """
        if value is None:
            return None
        normalized = str(value).strip().lower()
        return normalized or None

    def _identity_query(self, identity: str | None) -> dict:
        """Return identity lookup query using username as canonical key."""
        normalized = self._normalize_user_id(identity)
        if not normalized:
            return {"_id": None}
        return {"$or": [{"username": normalized}, {"user_id": normalized}]}

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
        doc = self.get_collection().find_one(self._identity_query(normalized))
        return dict(doc) if doc else None

    def ensure_username(self, user_data: dict) -> dict:
        """
        Ensure user payload contains explicit business key (`username`).
        """
        if not isinstance(user_data, dict):
            return user_data
        normalized = self._normalize_user_id(user_data.get("username"))
        if normalized:
            user_data["username"] = normalized
            return user_data
        raise ValueError("users.username is required in strict business-key mode")

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
            self._identity_query(normalized),
            {"$set": {"password": password_hash}},
        ):
            invalidate_dashboard_summary_cache(self.adapter)
            flash("Password updated", "green")
        else:
            flash("Failed to update password", "red")

    def user_exists(self, user_id=None, email=None, username=None) -> bool:
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

        identity = username or user_id
        if identity:
            normalized = self._normalize_user_id(identity)
            return bool(self.get_collection().find_one(self._identity_query(normalized)))

        return False

    def create_user(self, user_data: dict) -> None:
        """
        Inserts a new user document into the database.
        Args:
            user_data (dict): A dictionary containing user information to be stored.
        Returns:
            None
        """
        payload = self.ensure_username(dict(user_data))
        result = self.get_collection().insert_one(payload)
        invalidate_dashboard_summary_cache(self.adapter)
        return result

    def get_all_users(self) -> list:
        """
        Retrieve all users from the database, sorted by fullname in ascending order.
        Returns:
            list: A list of user documents.
        """
        return list(self.get_collection().find().sort("firstname", 1))

    def search_users(
        self, *, q: str = "", page: int = 1, per_page: int = 30
    ) -> tuple[list[dict], int]:
        """Search users directly in MongoDB and return paged results."""
        normalized_q = str(q or "").strip()
        query: dict = {}
        if normalized_q:
            pattern = re.escape(normalized_q)
            query["$or"] = [
                {"username": {"$regex": pattern, "$options": "i"}},
                {"email": {"$regex": pattern, "$options": "i"}},
                {"fullname": {"$regex": pattern, "$options": "i"}},
                {"firstname": {"$regex": pattern, "$options": "i"}},
                {"lastname": {"$regex": pattern, "$options": "i"}},
                {"role": {"$regex": pattern, "$options": "i"}},
                {"job_title": {"$regex": pattern, "$options": "i"}},
            ]
        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 30), 200))
        skip = (page - 1) * per_page
        col = self.get_collection()
        total = int(col.count_documents(query))
        docs = list(
            col.find(query).sort([("firstname", 1), ("username", 1)]).skip(skip).limit(per_page)
        )
        return docs, total

    def get_dashboard_user_rollup(self) -> dict:
        """
        Aggregate user counts/role breakdowns for dashboard payloads.
        """
        pipeline = [
            {
                "$facet": {
                    "counts": [
                        {
                            "$group": {
                                "_id": None,
                                "users_total": {"$sum": 1},
                                "users_active": {
                                    "$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]}
                                },
                            }
                        },
                        {"$project": {"_id": 0, "users_total": 1, "users_active": 1}},
                    ],
                    "role_counts": [
                        {
                            "$project": {
                                "role": {
                                    "$let": {
                                        "vars": {
                                            "normalized": {
                                                "$toLower": {
                                                    "$trim": {
                                                        "input": {"$ifNull": ["$role", "unknown"]},
                                                        "chars": " ",
                                                    }
                                                }
                                            }
                                        },
                                        "in": {
                                            "$cond": [
                                                {"$eq": ["$$normalized", ""]},
                                                "unknown",
                                                "$$normalized",
                                            ]
                                        },
                                    }
                                }
                            }
                        },
                        {"$group": {"_id": "$role", "count": {"$sum": 1}}},
                    ],
                    "profession_role": [
                        {
                            "$project": {
                                "role": {
                                    "$let": {
                                        "vars": {
                                            "normalized": {
                                                "$toLower": {
                                                    "$trim": {
                                                        "input": {"$ifNull": ["$role", "unknown"]},
                                                        "chars": " ",
                                                    }
                                                }
                                            }
                                        },
                                        "in": {
                                            "$cond": [
                                                {"$eq": ["$$normalized", ""]},
                                                "unknown",
                                                "$$normalized",
                                            ]
                                        },
                                    }
                                },
                                "profession": {
                                    "$let": {
                                        "vars": {
                                            "resolved": {
                                                "$ifNull": [
                                                    "$job_title",
                                                    {
                                                        "$ifNull": [
                                                            "$profession",
                                                            {"$ifNull": ["$title", "Unknown"]},
                                                        ]
                                                    },
                                                ]
                                            }
                                        },
                                        "in": {
                                            "$cond": [
                                                {
                                                    "$eq": [
                                                        {
                                                            "$trim": {
                                                                "input": {
                                                                    "$toString": "$$resolved"
                                                                },
                                                                "chars": " ",
                                                            }
                                                        },
                                                        "",
                                                    ]
                                                },
                                                "Unknown",
                                                {
                                                    "$trim": {
                                                        "input": {"$toString": "$$resolved"},
                                                        "chars": " ",
                                                    }
                                                },
                                            ]
                                        },
                                    }
                                },
                            }
                        },
                        {
                            "$group": {
                                "_id": {"profession": "$profession", "role": "$role"},
                                "count": {"$sum": 1},
                            }
                        },
                    ],
                }
            }
        ]

        doc = (list(self.get_collection().aggregate(pipeline, allowDiskUse=True)) or [{}])[0]
        counts_doc = (doc.get("counts") or [{}])[0]
        role_counts: dict[str, int] = {}
        for row in doc.get("role_counts", []) or []:
            role_counts[str(row.get("_id") or "unknown")] = int(row.get("count", 0) or 0)

        profession_role_matrix: dict[str, dict[str, int]] = {}
        for row in doc.get("profession_role", []) or []:
            key = row.get("_id") or {}
            profession = str(key.get("profession") or "Unknown")
            role = str(key.get("role") or "unknown")
            profession_role_matrix.setdefault(profession, {})
            profession_role_matrix[profession][role] = int(row.get("count", 0) or 0)

        return {
            "users_total": int(counts_doc.get("users_total", 0) or 0),
            "users_active": int(counts_doc.get("users_active", 0) or 0),
            "role_user_counts": role_counts,
            "profession_role_matrix": profession_role_matrix,
        }

    def delete_user(self, user_id) -> None:
        """
        Deletes a user from the database by their unique ID.
        Args:
            user_id: The unique identifier of the user to be deleted.
        Returns:
            None
        """
        normalized = self._normalize_user_id(user_id)
        result = self.get_collection().delete_one(self._identity_query(normalized))
        invalidate_dashboard_summary_cache(self.adapter)
        return result

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
        payload = self.ensure_username(dict(user_data))
        existing = self.get_collection().find_one(self._identity_query(normalized), {"_id": 1})
        if not existing:
            return None
        payload["_id"] = existing["_id"]
        result = self.get_collection().replace_one({"_id": existing["_id"]}, payload)
        invalidate_dashboard_summary_cache(self.adapter)
        return result

    def update_user_last_login(self, user_id: str):
        """
        Updates the last login timestamp for a user in the database.

        Args:
            user_id (str): The unique identifier of the user.
        """
        normalized = self._normalize_user_id(user_id)
        self.get_collection().update_one(
            self._identity_query(normalized),
            {"$set": {"last_login": datetime.now(timezone.utc)}},
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
            self._identity_query(normalized),
            {"$set": {"is_active": active_status}},
        )
        invalidate_dashboard_summary_cache(self.adapter)
        return bool(getattr(result, "modified_count", 0) or getattr(result, "matched_count", 0))

    def set_password_action_token(
        self,
        *,
        user_id: str,
        token_hash: str,
        purpose: str,
        expires_at: datetime,
        issued_by: str | None = None,
    ) -> None:
        """Persist one-time password token metadata."""
        normalized = self._normalize_user_id(user_id)
        payload = {
            "password_action_token_hash": str(token_hash),
            "password_action_purpose": str(purpose),
            "password_action_expires_at": expires_at,
            "password_action_issued_at": datetime.now(timezone.utc),
            "must_change_password": True,
        }
        if issued_by:
            payload["password_action_issued_by"] = str(issued_by)
        self.get_collection().update_one(
            self._identity_query(normalized),
            {"$set": payload},
        )

    def validate_and_clear_password_action_token(
        self, *, user_id: str, token_hash: str, purpose: str
    ) -> bool:
        """Validate token metadata and clear it when valid."""
        normalized = self._normalize_user_id(user_id)
        now = datetime.now(timezone.utc)
        user = self.get_collection().find_one(self._identity_query(normalized))
        if not user:
            return False

        expected_hash = str(user.get("password_action_token_hash") or "")
        expected_purpose = str(user.get("password_action_purpose") or "")
        expires_at = user.get("password_action_expires_at")
        if (
            expected_hash != str(token_hash)
            or expected_purpose != str(purpose)
            or not expires_at
            or now > expires_at
        ):
            return False

        self.get_collection().update_one(
            self._identity_query(normalized),
            {
                "$unset": {
                    "password_action_token_hash": "",
                    "password_action_purpose": "",
                    "password_action_expires_at": "",
                    "password_action_issued_at": "",
                    "password_action_issued_by": "",
                }
            },
        )
        return True

    def set_local_password(
        self, *, user_id: str, password_hash: str, require_password_change: bool = False
    ) -> None:
        """Update local password hash and auth metadata."""
        normalized = self._normalize_user_id(user_id)
        self.get_collection().update_one(
            self._identity_query(normalized),
            {
                "$set": {
                    "password": str(password_hash),
                    "auth_type": "coyote3",
                    "must_change_password": bool(require_password_change),
                    "password_updated_on": datetime.now(timezone.utc),
                },
                "$unset": {
                    "password_action_token_hash": "",
                    "password_action_purpose": "",
                    "password_action_expires_at": "",
                    "password_action_issued_at": "",
                    "password_action_issued_by": "",
                },
            },
        )
