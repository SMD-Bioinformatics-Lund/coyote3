from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Set
from datetime import datetime
from werkzeug.security import check_password_hash


class UserModel(BaseModel):
    id: str = Field(..., alias="_id")
    email: EmailStr
    username: str
    fullname: str
    role: str
    assay_groups: List[str] = []
    assays: List[str] = []
    asp_map: dict = {}
    envs: List[str] = []
    permissions: List[str] = []
    denied_permissions: List[str] = []
    access_level: int = 0
    job_title: Optional[str] = None
    is_active: bool = True

    # -------------------- STATIC METHODS --------------------
    @staticmethod
    def validate_login(stored_hash: str, plain_password: str) -> bool:
        return check_password_hash(stored_hash, plain_password)

    @classmethod
    def from_mongo(
        cls,
        user_doc: dict,
        role_doc: Optional[dict] = None,
        asp_docs: Optional[List[dict]] = None,
    ) -> "UserModel":
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
                asp_technology = "panels"
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
        return self.dict(
            by_alias=True,
            exclude={"updated", "created", "last_login", "password"},
            exclude_none=True,
        )

    # -------------------- PROPERTIES & HELPERS --------------------
    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions and perm not in self.denied_permissions

    def has_any_permission(self, perms: List[str]) -> bool:
        return any(p in self.permissions for p in perms)

    def has_all_permissions(self, perms: List[str]) -> bool:
        return all(p in self.permissions for p in perms)

    def has_min_access_level(self, level: int) -> bool:
        return self.access_level >= level

    def has_min_role_priority(self, required_priority: int) -> bool:
        return self.access_level >= required_priority

    @property
    def granted_permissions(self) -> Set[str]:
        return set(self.permissions) - set(self.denied_permissions)

    @property
    def forbidden_permissions(self) -> Set[str]:
        return set(self.denied_permissions)

    @property
    def is_admin(self):
        return self.role == "admin"

    def can_access_group(self, group: str) -> bool:
        return self.role == "admin" or group in self.assay_groups

    def can_access_assay(self, assay: str) -> bool:
        return self.role == "admin" or assay in self.assays

    def get_accessible_groups(self) -> List[str]:
        return ["ALL"] if self.role == "admin" else self.assay_groups

    def formatted_last_login(self) -> Optional[str]:
        return (
            self.last_login.strftime("%Y-%m-%d %H:%M:%S")
            if self.last_login
            else None
        )

    def formatted_created(self) -> Optional[str]:
        return (
            self.created.strftime("%Y-%m-%d %H:%M:%S")
            if self.created
            else None
        )

    def formatted_updated(self) -> Optional[str]:
        return (
            self.updated.strftime("%Y-%m-%d %H:%M:%S")
            if self.updated
            else None
        )

    class Config:
        validate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}
