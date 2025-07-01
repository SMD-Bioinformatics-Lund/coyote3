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
Coyote3 User Model

This module defines the `UserModel` class, representing user entities within the Coyote3 system.
It provides methods for authentication, permission checks, and access control, as well as utilities
for serializing user data and formatting timestamps. The model is designed for integration with
MongoDB and supports merging user, role, and assay-specific permissions and attributes.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Set
from datetime import datetime
from werkzeug.security import check_password_hash


class UserModel(BaseModel):
    """
    UserModel represents a user entity within the Coyote3 system,
    encapsulating user identity, roles, permissions, and access controls for genomic data analysis and diagnostics.
    """

    id: str = Field(..., alias="_id")
    email: EmailStr
    username: str
    fullname: str
    role: str
    assay_groups: List[str] = []
    assays: List[str] = []
    asp_map: dict = {}
    environments: List[str] = []
    permissions: List[str] = []
    denied_permissions: List[str] = []
    access_level: int = 0
    job_title: Optional[str] = None
    is_active: bool = True

    # -------------------- STATIC METHODS --------------------
    @staticmethod
    def validate_login(stored_hash: str, plain_password: str) -> bool:
        """
        Validate a plain password against a stored password hash.

        Args:
            stored_hash (str): The hashed password stored in the database.
            plain_password (str): The plain text password to validate.

        Returns:
            bool: True if the password matches the hash, False otherwise.
        """
        return check_password_hash(stored_hash, plain_password)

    @classmethod
    def from_mongo(
        cls,
        user_doc: dict,
        role_doc: Optional[dict] = None,
        asp_docs: Optional[List[dict]] = None,
    ) -> "UserModel":
        """
        Constructs a UserModel instance from MongoDB user, role, and ASP documents.

        Args:
            cls: The class reference (UserModel).
            user_doc (dict): The user document from MongoDB.
            role_doc (Optional[dict]): The role document from MongoDB. Defaults to empty dict if not provided.
            asp_docs (Optional[List[dict]]): List of ASP documents from MongoDB. Defaults to empty list if not provided.

        Returns:
            UserModel: An instance of `UserModel` populated with merged user, role, and ASP data.
        """
        role_doc = role_doc or {}
        asp_docs = asp_docs or []

        asp_map = {}
        for asp in asp_docs:
            asp_category = asp.get("asp_category", "NA")
            asp_group = asp.get("asp_group", "unassigned")
            asp_name = asp.get("_id")

            if asp_name not in user_doc.get("assays", []):
                continue

            if "Panel" in asp.get("asp_family", "NA"):
                asp_technology = "asp"
            else:
                asp_technology = asp.get("asp_family", "NA")

            if asp_category not in asp_map:
                asp_map[asp_category] = {}
            if asp_technology not in asp_map[asp_category]:
                asp_map[asp_category][asp_technology] = {}
            if asp_group not in asp_map[asp_category][asp_technology]:
                asp_map[asp_category][asp_technology][asp_group] = []

            asp_map[asp_category][asp_technology][asp_group].append(asp_name)

        merged_permissions = list(
            set(user_doc.get("permissions", []))
            | set(role_doc.get("permissions", []))
        )
        merged_denied = list(
            set(user_doc.get("denied_permissions", []))
            | set(role_doc.get("denied_permissions", []))
        )

        safe_user_doc = {
            k: v
            for k, v in user_doc.items()
            if k
            not in {
                "permissions",
                "denied_permissions",
                "access_level",
                "asp_map",
            }
        }

        return cls(
            **safe_user_doc,
            permissions=merged_permissions,
            denied_permissions=merged_denied,
            access_level=role_doc.get("level", 0),
            asp_map=asp_map,
        )

    def to_dict(self) -> dict:
        """
        Returns a dictionary representation of the UserModel instance, excluding sensitive fields
        such as updated, created, last_login, and password. Uses field aliases and omits
        fields with `None` values.

        Returns:
            dict: A sanitized dictionary of the user data.
        """
        return self.dict(
            by_alias=True,
            exclude={"updated", "created", "last_login", "password"},
            exclude_none=True,
        )

    # -------------------- PROPERTIES & HELPERS --------------------
    def has_permission(self, perm: str) -> bool:
        """
        Determines if the user has a specific permission.

        This method checks whether the given permission is present in the user's granted permissions
        and not explicitly listed in the denied permissions.

        Args:
            perm (str): The permission to check.

        Returns:
            bool: True if the user has the permission and it is not denied, False otherwise.
        """
        return perm in self.permissions and perm not in self.denied_permissions

    def has_any_permission(self, perms: List[str]) -> bool:
        """
        Checks if the user has any of the specified permissions.

        Args:
            perms (List[str]): A list of permissions to check.

        Returns:
            bool: True if the user has at least one of the specified permissions, False otherwise.
        """
        return any(p in self.permissions for p in perms)

    def has_all_permissions(self, perms: List[str]) -> bool:
        """
        Checks if the user has all of the specified permissions.

        Args:
            perms (List[str]): A list of permissions to check.

        Returns:
            bool: True if the user has all of the specified permissions, False otherwise.
        """
        return all(p in self.permissions for p in perms)

    def has_min_access_level(self, level: int) -> bool:
        """
        Checks if the user's access level is greater than or equal to the specified level.

        Args:
            level (int): The minimum access level required.

        Returns:
            bool: True if the user's access level is sufficient, False otherwise.
        """
        return self.access_level >= level

    def has_min_role_priority(self, required_priority: int) -> bool:
        """
        Checks if the user's role priority (access level) is greater than or equal to the required priority.

        Args:
            required_priority (int): The minimum role priority (access level) required.

        Returns:
            bool: True if the user's access level is sufficient, False otherwise.
        """
        return self.access_level >= required_priority

    @property
    def granted_permissions(self) -> Set[str]:
        """
        Returns the set of permissions granted to the user, excluding any permissions that are explicitly denied.

        Returns:
            Set[str]: The effective permissions available to the user.
        """
        return set(self.permissions) - set(self.denied_permissions)

    @property
    def forbidden_permissions(self) -> Set[str]:
        """
        Returns the set of permissions explicitly denied to the user.

        Returns:
            Set[str]: The set of denied permissions for the user.
        """
        return set(self.denied_permissions)

    @property
    def is_admin(self) -> bool:
        """
        Checks if the user has the 'admin' role.

        Returns:
            bool: True if the user's role is 'admin', False otherwise.
        """
        return self.role == "admin"

    @property
    def envs(self) -> List[str]:
        """
        Returns the list of environments the user has access to.
        If no environments are specified, defaults to ["production"].

        Returns:
            List[str]: List of environment names.
        """
        return self.environments if self.environments else ["production"]

    def can_access_group(self, group: str) -> bool:
        """
        Determines if the user can access a specific assay group.

        Args:
            group (str): The assay group to check access for.

        Returns:
            bool: True if the user is an admin or the group is in the user's assay groups, False otherwise.
        """
        return self.role == "admin" or group in self.assay_groups

    def can_access_assay(self, assay: str) -> bool:
        """
        Determines if the user can access a specific assay.

        Args:
            assay (str): The assay to check access for.

        Returns:
            bool: True if the user is an admin or the assay is in the user's assays, False otherwise.
        """
        return self.role == "admin" or assay in self.assays

    def get_accessible_groups(self) -> List[str]:
        """
        Returns a list of assay groups the user can access.

        If the user's role is 'admin', returns ["ALL"] to indicate access to all groups.
        Otherwise, returns the user's specific assay groups.

        Returns:
            List[str]: Accessible assay groups for the user.
        """
        return ["ALL"] if self.role == "admin" else self.assay_groups

    def formatted_last_login(self) -> Optional[str]:
        """
        Returns the user's last login time as a formatted string.

        Returns:
            Optional[str]: The last login timestamp in '%Y-%m-%d %H:%M:%S' format, or None if not set.
        """
        return (
            self.last_login.strftime("%Y-%m-%d %H:%M:%S")
            if self.last_login
            else None
        )

    def formatted_created(self) -> Optional[str]:
        """
        Returns the user's creation time as a formatted string.

        Returns:
            Optional[str]: The creation timestamp in '%Y-%m-%d %H:%M:%S' format, or None if not set.
        """
        return (
            self.created.strftime("%Y-%m-%d %H:%M:%S")
            if self.created
            else None
        )

    def formatted_updated(self) -> Optional[str]:
        """
        Returns the user's last updated time as a formatted string.

        Returns:
            Optional[str]: The updated timestamp in '%Y-%m-%d %H:%M:%S' format, or None if not set.
        """
        return (
            self.updated.strftime("%Y-%m-%d %H:%M:%S")
            if self.updated
            else None
        )

    class Config:
        """
        Pydantic configuration for UserModel.

        - validate_by_name: Allows population and validation using field names as well as aliases.
        - json_encoders: Custom encoder for `datetime` objects to ensure ISO 8601 string output during serialization.
        """

        validate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}
