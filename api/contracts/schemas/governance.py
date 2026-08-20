"""Access-control and schema-definition contracts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.config.constants import (
    DEFAULT_AUTH_PROVIDER,
    normalize_asp_group,
    normalize_auth_types,
    normalize_environment,
    normalize_permission_category,
)
from api.contracts.schemas.base import _StrictDocBase


class UserUiSettingsDoc(BaseModel):
    """Persisted presentation preferences for one user."""

    model_config = ConfigDict(extra="forbid")

    analysis_layout: str = "classic"
    sample_list_layout: str = "classic"
    analysis_modern_view_tried: bool = False
    sample_list_modern_view_tried: bool = False

    @field_validator("analysis_layout")
    @classmethod
    def _validate_analysis_layout(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"classic", "modern"}:
            raise ValueError("analysis_layout must be one of: classic, modern")
        return normalized

    @field_validator("sample_list_layout")
    @classmethod
    def _validate_sample_list_layout(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"classic", "modern"}:
            raise ValueError("sample_list_layout must be one of: classic, modern")
        return normalized


class UsersDoc(_StrictDocBase):
    email: str
    username: str
    firstname: str
    lastname: str
    fullname: str
    job_title: str
    auth_type: list[str] = Field(default_factory=lambda: [DEFAULT_AUTH_PROVIDER])
    password: str | None = None
    last_login: datetime | None = None
    must_change_password: bool = False
    password_updated_on: datetime | None = None
    password_action_token_hash: str | None = None
    password_action_purpose: str | None = None
    password_action_expires_at: datetime | None = None
    password_action_issued_at: datetime | None = None
    password_action_issued_by: str | None = None
    roles: list[str] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)
    asp_ids: list[str] = Field(default_factory=list)
    asp_groups: list[str] = Field(default_factory=list)
    ui_settings: UserUiSettingsDoc = Field(default_factory=UserUiSettingsDoc)
    is_active: bool = True
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("email must contain '@'")
        return value.strip().lower()

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if not normalized:
            raise ValueError("username is required")
        if not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", normalized):
            raise ValueError(
                "username may contain only lowercase letters, numbers, '.', '_' and '-'"
            )
        return normalized

    @field_validator("roles", mode="before")
    @classmethod
    def _normalize_roles(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (str, bytes)):
            value = [value]
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            role_id = str(item or "").strip().lower()
            if role_id and role_id not in seen:
                normalized.append(role_id)
                seen.add(role_id)
        return normalized

    @field_validator("auth_type", mode="before")
    @classmethod
    def _normalize_auth_type(cls, value: Any) -> list[str]:
        return normalize_auth_types(value)

    @field_validator("environments", mode="before")
    @classmethod
    def _normalize_environments(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, (str, bytes)):
            value = [value]
        normalized: list[str] = []
        for item in value:
            normalized.append(normalize_environment(item, label="environments"))
        return normalized

    @field_validator("asp_groups", mode="before")
    @classmethod
    def _normalize_asp_groups(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (str, bytes)):
            value = [value]
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            group = normalize_asp_group(item)
            if group not in seen:
                normalized.append(group)
                seen.add(group)
        return normalized


class RolesDoc(_StrictDocBase):
    role_id: str
    name: str
    label: str
    description: str | None = None
    color: str
    level: int | float
    is_active: bool = True
    permissions: list[str] = Field(default_factory=list)
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None

    @field_validator("role_id", "name", mode="before")
    @classmethod
    def _normalize_role_id(cls, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if not normalized:
            raise ValueError("role_id/name is required")
        if not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", normalized):
            raise ValueError(
                "role identifiers may contain lowercase letters, numbers, '.', '_' and '-'"
            )
        return normalized

    @field_validator("permissions", mode="before")
    @classmethod
    def _normalize_permissions(cls, value: Any) -> list[str]:
        return _normalize_permission_ids(value)

    @field_validator("color", mode="before")
    @classmethod
    def _normalize_color(cls, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if re.fullmatch(r"#[0-9a-f]{6}", normalized):
            return normalized
        # Preserve named colors already stored by earlier releases. New color
        # picker selections are always persisted as explicit hex values.
        if re.fullmatch(r"[a-z][a-z0-9_-]*", normalized):
            return normalized
        raise ValueError("color must be a six-digit #RRGGBB value")


class PermissionsDoc(_StrictDocBase):
    permission_id: str
    label: str
    category: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    system_managed: bool = False
    is_active: bool = True
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, value: Any) -> str:
        return normalize_permission_category(value)

    @field_validator("permission_id", mode="before")
    @classmethod
    def _normalize_permission_id(cls, value: Any) -> str:
        permission_id = str(value or "").strip().lower()
        if not permission_id:
            raise ValueError("permission_id is required")
        if not re.fullmatch(r"[a-z0-9_.]+:[a-z0-9_.]+(?::[a-z0-9_.]+)*", permission_id):
            raise ValueError("permission_id must use resource:action[:scope] format")
        return permission_id


def _normalize_permission_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        value = [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        permission_id = str(item or "").strip().lower()
        if permission_id and permission_id not in seen:
            normalized.append(permission_id)
            seen.add(permission_id)
    return normalized
