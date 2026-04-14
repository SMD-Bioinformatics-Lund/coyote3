"""User model and auth/session shaping helpers."""

from datetime import datetime
from typing import List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, field_validator
from werkzeug.security import check_password_hash


def _unique_permission_ids(permission_ids: list[str] | None) -> list[str]:
    """Normalize and deduplicate permission ids read from persistence."""
    normalized_ids: list[str] = []
    seen: set[str] = set()
    for permission_id in permission_ids or []:
        value = str(permission_id or "").strip().lower()
        if value and value not in seen:
            normalized_ids.append(value)
            seen.add(value)
    return normalized_ids


def _unique_role_ids(role_ids: list[str] | None) -> list[str]:
    """Normalize and deduplicate role ids read from persistence."""
    normalized_roles: list[str] = []
    seen: set[str] = set()
    for role_id in role_ids or []:
        value = str(role_id or "").strip().lower()
        if value and value not in seen:
            normalized_roles.append(value)
            seen.add(value)
    return normalized_roles


class UserModel(BaseModel):
    """
    UserModel represents a user entity within the Coyote3 system,
    encapsulating user identity, roles, permissions, and access controls for genomic data analysis and diagnostics.
    """

    model_config = ConfigDict(
        validate_by_name=True,
        populate_by_name=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )

    id: str = Field(..., alias="_id")
    email: str
    username: str
    fullname: str
    roles: List[str] = Field(default_factory=list)
    role: str = ""
    assay_groups: List[str] = Field(default_factory=list)
    assays: List[str] = Field(default_factory=list)
    asp_map: dict = Field(default_factory=dict)
    environments: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    denied_permissions: List[str] = Field(default_factory=list)
    access_level: int = 0
    job_title: Optional[str] = None
    is_active: bool = True
    auth_type: Optional[str] = "coyote3"
    must_change_password: bool = False

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id_to_str(cls, value):
        """Normalize provider-backed id values into canonical string ids."""
        if value is None:
            return value
        return str(value)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value):
        """Accept center-local addresses while enforcing basic email structure."""
        email = str(value or "").strip().lower()
        if not email or "@" not in email:
            raise ValueError("email must contain '@'")
        local, domain = email.split("@", 1)
        if not local or not domain:
            raise ValueError("email must include local and domain parts")
        return email

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
    def from_auth_payload(
        cls,
        user_doc: dict,
        role_docs: Optional[List[dict]] = None,
        asp_docs: Optional[List[dict]] = None,
    ) -> "UserModel":
        """
        Construct a user model from auth-related data payloads.

        Args:
            cls: The class reference (UserModel).
            user_doc (dict): The user payload from persistence.
            role_docs (Optional[List[dict]]): Role payloads from persistence.
            asp_docs (Optional[List[dict]]): Active assay payloads from persistence.

        Returns:
            UserModel: An instance populated with merged user, role, and assay data.
        """
        role_docs = [dict(item) for item in (role_docs or []) if isinstance(item, dict)]
        asp_docs = asp_docs or []

        asp_map = {}
        for asp in asp_docs:
            asp_category = asp.get("asp_category", "NA")
            asp_group = asp.get("asp_group", "unassigned")
            asp_name = asp.get("asp_id")

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

        user_roles = _unique_role_ids(user_doc.get("roles") or [])
        role_permissions: list[str] = []
        role_denied_permissions: list[str] = []
        effective_role = ""
        access_level = 0
        for role_doc in role_docs:
            role_permissions.extend(list(role_doc.get("permissions", [])))
            role_denied_permissions.extend(list(role_doc.get("deny_permissions", [])))
            role_level = int(role_doc.get("level", 0) or 0)
            role_name = str(role_doc.get("role_id") or "").strip().lower()
            if role_level >= access_level:
                access_level = role_level
                effective_role = role_name
        if "superuser" in user_roles:
            effective_role = "superuser"

        merged_permissions = _unique_permission_ids(
            list(user_doc.get("permissions", [])) + role_permissions
        )
        merged_denied = _unique_permission_ids(
            list(user_doc.get("deny_permissions", []))
            + list(user_doc.get("denied_permissions", []))
            + role_denied_permissions
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
                "roles",
                "role",
            }
        }
        return cls(
            **safe_user_doc,
            roles=user_roles,
            role=effective_role,
            permissions=merged_permissions,
            denied_permissions=merged_denied,
            access_level=access_level,
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
        payload = self.model_dump(
            by_alias=True,
            exclude={"updated", "created", "last_login", "password"},
            exclude_none=True,
        )
        payload["_id"] = self.username
        return payload

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
        if not perm:
            return False
        if self.is_superuser:
            return True
        return perm in self.permissions and perm not in self.denied_permissions

    def has_any_permission(self, perms: List[str]) -> bool:
        """
        Checks if the user has any of the specified permissions.

        Args:
            perms (List[str]): A list of permissions to check.

        Returns:
            bool: True if the user has at least one of the specified permissions, False otherwise.
        """
        return any(self.has_permission(p) for p in perms)

    def has_all_permissions(self, perms: List[str]) -> bool:
        """
        Checks if the user has all of the specified permissions.

        Args:
            perms (List[str]): A list of permissions to check.

        Returns:
            bool: True if the user has all of the specified permissions, False otherwise.
        """
        return all(self.has_permission(p) for p in perms)

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
    def is_superuser(self) -> bool:
        """Return whether the user carries the unrestricted superuser role."""
        return "superuser" in set(self.roles)

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
            bool: True if the user is a superuser or the group is in the user's assay groups, False otherwise.
        """
        return self.is_superuser or group in self.assay_groups

    def can_access_assay(self, assay: str) -> bool:
        """
        Determines if the user can access a specific assay.

        Args:
            assay (str): The assay to check access for.

        Returns:
            bool: True if the user is a superuser or the assay is in the user's assays, False otherwise.
        """
        return self.is_superuser or assay in self.assays

    def get_accessible_groups(self) -> List[str]:
        """
        Returns a list of assay groups the user can access.

        If the user is a superuser, returns ["ALL"] to indicate access to all groups.
        Otherwise, returns the user's specific assay groups.

        Returns:
            List[str]: Accessible assay groups for the user.
        """
        return ["ALL"] if self.is_superuser else self.assay_groups
