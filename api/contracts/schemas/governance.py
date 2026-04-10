"""Access-control and schema-definition contracts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import AliasChoices, Field, field_validator

from api.contracts.schemas.base import VersionHistoryEntryDoc, _StrictDocBase


class UsersDoc(_StrictDocBase):
    email: str
    username: str
    firstname: str
    lastname: str
    fullname: str
    job_title: str
    auth_type: Literal["coyote3", "ldap"] | None = "coyote3"
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
    environments: list[Literal["production", "development", "testing", "validation"]] = Field(
        default_factory=list
    )
    assays: list[str] = Field(default_factory=list)
    assay_groups: list[str] = Field(default_factory=list)
    is_active: bool = True
    permissions: list[str] = Field(default_factory=list)
    deny_permissions: list[str] = Field(
        validation_alias=AliasChoices("deny_permissions", "denied_permissions"),
        default_factory=list,
    )
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None
    version_history: list[VersionHistoryEntryDoc] = Field(default_factory=list)

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

    @field_validator("environments", mode="before")
    @classmethod
    def _normalize_environments(cls, value: Any) -> Any:
        if value is None:
            return []
        aliases = {
            "prod": "production",
            "p": "production",
            "production": "production",
            "dev": "development",
            "development": "development",
            "d": "development",
            "test": "testing",
            "testing": "testing",
            "t": "testing",
            "validation": "validation",
            "stage": "validation",
            "staging": "validation",
            "v": "validation",
        }
        normalized: list[str] = []
        for item in value:
            key = str(item).strip().lower()
            if key not in aliases:
                raise ValueError(
                    "environments must be in: production, development, testing, validation"
                )
            normalized.append(aliases[key])
        return normalized


class RolesDoc(_StrictDocBase):
    role_id: str
    name: str
    label: str
    description: str | None = None
    color: str  # yes
    level: int | float  # yes
    is_active: bool = True
    permissions: list[str] = Field(default_factory=list)
    deny_permissions: list[str] = Field(default_factory=list)
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None
    version_history: list[VersionHistoryEntryDoc] = Field(default_factory=list)


class PermissionsDoc(_StrictDocBase):
    permission_id: str
    permission_name: str
    label: str
    category: str
    description: str | None = None
    tags: list[str]
    is_active: bool = True
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None
    version_history: list[VersionHistoryEntryDoc] = Field(default_factory=list)
