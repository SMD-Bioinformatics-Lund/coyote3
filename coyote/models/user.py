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
    groups: List[str] = []
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
    def from_mongo(cls, user_doc: dict, role_doc: Optional[dict] = None) -> "UserModel":
        role_doc = role_doc or {}

        merged_permissions = list(
            set(user_doc.get("permissions", [])) | set(role_doc.get("permissions", []))
        )
        merged_denied = list(
            set(user_doc.get("denied_permissions", []))
            | set(role_doc.get("denied_permissions", []))
        )

        safe_user_doc = {
            k: v
            for k, v in user_doc.items()
            if k not in {"permissions", "denied_permissions", "access_level"}
        }

        return cls(
            **safe_user_doc,
            permissions=merged_permissions,
            denied_permissions=merged_denied,
            access_level=role_doc.get("level", 0),
        )

    def to_dict(self) -> dict:
        return self.dict(
            by_alias=True,
            exclude={"updated", "created", "last_login", "password"},
            exclude_none=True,  # 🔥 this is the magic that removes None fields
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
        return self.role == "admin" or group in self.groups

    def get_accessible_groups(self) -> List[str]:
        return ["ALL"] if self.role == "admin" else self.groups

    def formatted_last_login(self) -> Optional[str]:
        return self.last_login.strftime("%Y-%m-%d %H:%M:%S") if self.last_login else None

    def formatted_created(self) -> Optional[str]:
        return self.created.strftime("%Y-%m-%d %H:%M:%S") if self.created else None

    def formatted_updated(self) -> Optional[str]:
        return self.updated.strftime("%Y-%m-%d %H:%M:%S") if self.updated else None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}
