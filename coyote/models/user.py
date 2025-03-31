from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class AppRole(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    TESTER = "tester"
    GROUP_MANAGER = "group_manager"
    STANDARD_USER = "standard_user"
    VIEWER = "viewer"
    EXTERNAL = "external"


class UserModel(BaseModel):
    id: str = Field(..., alias="_id")  # MongoDB uses "_id"
    email: str = Field(..., alias="email")  # MongoDB uses "email"
    fullname: str
    job_title: Optional[str] = None  # e.g. "Clinical Geneticist"
    role: AppRole
    groups: List[str] = []
    permissions: List[str] = []
    password: Optional[str] = None
    updated: Optional[datetime] = None
    created: Optional[datetime] = None
    last_login: Optional[datetime] = None
    is_active: bool = True

    def in_group(self, group: str) -> bool:
        return group in self.groups

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions

    def has_any_permission(self, perms: List[str]) -> bool:
        return any(p in self.permissions for p in perms)

    @property
    def username(self) -> bool:
        return self.id

    @property
    def is_admin(self) -> bool:
        return self.role == AppRole.ADMIN

    @property
    def is_developer_or_tester(self) -> bool:
        return self.role in {AppRole.DEVELOPER, AppRole.TESTER}

    @property
    def is_group_manager(self) -> bool:
        return self.role == AppRole.GROUP_MANAGER

    @property
    def is_standard_user(self) -> bool:
        return self.role == AppRole.STANDARD_USER

    @property
    def is_viewer(self) -> bool:
        return self.role == AppRole.VIEWER

    @property
    def is_external(self) -> bool:
        return self.role == AppRole.EXTERNAL

    @property
    def can_manage_group(self) -> bool:
        return self.role in {AppRole.ADMIN, AppRole.GROUP_MANAGER}

    @property
    def has_limited_readonly_access(self) -> bool:
        return self.role in {AppRole.VIEWER, AppRole.EXTERNAL}

    model_config = {
        "validate_by_name": True,
        "populate_by_name": True,
        "json_encoders": {datetime: lambda v: v.isoformat()},
    }

    def update_last_login(self):
        self.last_login = datetime.utcnow()

    def formatted_last_login(self) -> Optional[str]:
        return self.last_login.strftime("%Y-%m-%d %H:%M:%S") if self.last_login else None

    def formatted_created(self) -> Optional[str]:
        return self.created.strftime("%Y-%m-%d %H:%M:%S") if self.created else None

    def formatted_updated(self) -> Optional[str]:
        return self.updated.strftime("%Y-%m-%d %H:%M:%S") if self.updated else None
