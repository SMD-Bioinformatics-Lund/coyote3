# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Access-control and schema-definition contracts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from coyote.config.constants import (
    DEFAULT_AUTH_PROVIDER,
    normalize_asp_group,
    normalize_auth_types,
    normalize_environment,
    normalize_permission_category,
)
from coyote.config.factory_defaults import factory_value
from coyote.contracts.auth import PasswordRecoveryRecord
from coyote.contracts.schemas.assay_access import AssayAccessGrant
from coyote.contracts.schemas.base import _StrictCollectionDocBase


class UserUiSettingsDoc(BaseModel):
    """Explicit user preferences; unset fields are omitted for frontend defaults."""

    model_config = ConfigDict(extra="forbid")

    analysis_layout: str | None = Field(default=None, exclude_if=lambda value: value is None)
    sample_list_layout: str | None = Field(default=None, exclude_if=lambda value: value is None)
    analysis_modern_view_tried: bool | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    sample_list_modern_view_tried: bool | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    table_page_size: int | None = Field(
        default=None,
        ge=1,
        le=factory_value("pagination.max_page_size"),
        exclude_if=lambda value: value is None,
    )
    theme: Literal["auto", "light", "dark"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @field_validator("analysis_layout")
    @classmethod
    def _validate_analysis_layout(cls, value: str | None) -> str | None:
        """Normalize a analysis layout preference.

        Args:
            value: Layout name before normalization, or None for an unset preference.

        Returns:
            The lowercase classic or modern layout name, or None when unset.

        Raises:
            ValueError: If the layout is neither classic nor modern.
        """
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized not in {"classic", "modern"}:
            raise ValueError("analysis_layout must be one of: classic, modern")
        return normalized

    @field_validator("sample_list_layout")
    @classmethod
    def _validate_sample_list_layout(cls, value: str | None) -> str | None:
        """Normalize a sample-list layout preference.

        Args:
            value: Layout name before normalization, or None for an unset preference.

        Returns:
            The lowercase classic or modern layout name, or None when unset.

        Raises:
            ValueError: If the layout is neither classic nor modern.
        """
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized not in {"classic", "modern"}:
            raise ValueError("sample_list_layout must be one of: classic, modern")
        return normalized


class UsersDoc(_StrictCollectionDocBase):
    """Persisted user identity, authentication state, access scope, and UI preferences."""

    email: str
    username: str
    firstname: str
    lastname: str
    fullname: str
    job_title: str
    auth_type: list[str] = Field(default_factory=lambda: [DEFAULT_AUTH_PROVIDER])
    password: str | None = None
    last_login: datetime | None = None
    must_change_password: bool = factory_value("governance_defaults.must_change_password")
    password_updated_on: datetime | None = None
    password_recovery: PasswordRecoveryRecord | None = None
    password_action_token_hash: str | None = None
    password_action_purpose: str | None = None
    password_action_expires_at: datetime | None = None
    password_action_issued_at: datetime | None = None
    password_action_issued_by: str | None = None
    roles: list[str] = Field(default_factory=list)
    assay_access: list[AssayAccessGrant] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)
    asp_ids: list[str] = Field(default_factory=list)
    asp_groups: list[str] = Field(default_factory=list)
    ui_settings: UserUiSettingsDoc = Field(default_factory=UserUiSettingsDoc)
    system_managed: bool = factory_value("records.system_managed")
    is_active: bool = factory_value("records.is_active")
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None

    @field_validator("assay_access")
    @classmethod
    def unique_assay_access(cls, values: list[AssayAccessGrant]) -> list[AssayAccessGrant]:
        """Require one authoritative environment row per assay."""
        if len({row.asp_id for row in values}) != len(values):
            raise ValueError("Assay access must contain one row per assay")
        return values

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        """Require an at-sign and canonicalize the stored email text.

        Args:
            value: Email text supplied for the user.

        Returns:
            The stripped, lowercase text.

        Raises:
            ValueError: If the text contains no at-sign.

        Notes:
            This is not full email-address syntax validation.
        """
        if "@" not in value:
            raise ValueError("email must contain '@'")
        return value.strip().lower()

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        """Canonicalize a username and validate its separator placement.

        Args:
            value: Required identifier before whitespace and case normalization.

        Returns:
            Lowercase alphanumeric segments separated by single dots, underscores, or hyphens.

        Raises:
            ValueError: If blank, malformed, or containing other characters.
        """
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
        """Strip, lowercase, and deduplicate role identifiers.

        Args:
            value: Identifier or iterable; None produces an empty list.

        Returns:
            Nonblank identifiers in first-occurrence order without checking their syntax.
        """
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
        """Resolve authentication providers against the configured vocabulary.

        Args:
            value: Provider or iterable; None or an empty iterable selects the default provider.

        Returns:
            Canonical provider IDs in first-occurrence order.

        Raises:
            ValueError: If a provider is blank or unsupported.
        """
        return normalize_auth_types(value)

    @field_validator("environments", mode="before")
    @classmethod
    def _normalize_environments(cls, value: Any) -> Any:
        """Validate and lowercase each environment in a user's access scope.

        Args:
            value: Environment or iterable; None produces an empty list.

        Returns:
            Configured environment IDs in input order, retaining duplicates.

        Raises:
            ValueError: If an environment is blank or unsupported.
        """
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
        """Validate and deduplicate a user's assay-group scope.

        Args:
            value: Assay group or iterable; None produces an empty list.

        Returns:
            Canonical configured groups in first-occurrence order.

        Raises:
            ValueError: If a group is blank or unsupported.
        """
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


class RolesDoc(_StrictCollectionDocBase):
    """Versioned role definition with permission membership, level, and display color."""

    role_id: str
    name: str
    label: str
    description: str | None = None
    color: str
    level: int | float
    system_managed: bool = factory_value("records.system_managed")
    is_active: bool = factory_value("records.is_active")
    permissions: list[str] = Field(default_factory=list)
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None

    @field_validator("role_id", "name", mode="before")
    @classmethod
    def _normalize_role_id(cls, value: Any) -> str:
        """Canonicalize a role identifier or name and validate its separator placement.

        Args:
            value: Required identifier before whitespace and case normalization.

        Returns:
            Lowercase alphanumeric segments separated by single dots, underscores, or hyphens.

        Raises:
            ValueError: If blank, malformed, or containing other characters.
        """
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
        """Strip, lowercase, and deduplicate permission identifiers.

        Args:
            value: Identifier or iterable; None produces an empty list.

        Returns:
            Nonblank identifiers in first-occurrence order without checking their syntax.
        """
        return _normalize_permission_ids(value)

    @field_validator("color", mode="before")
    @classmethod
    def _normalize_color(cls, value: Any) -> str:
        """Require the canonical six-digit hexadecimal role color.

        Args:
            value: Role color before whitespace and case normalization.

        Returns:
            The stripped, lowercase hexadecimal color.

        Raises:
            ValueError: If the value is not a six-digit hexadecimal color.
        """
        normalized = str(value or "").strip().lower()
        if re.fullmatch(r"#[0-9a-f]{6}", normalized):
            return normalized
        raise ValueError("color must be a six-digit #RRGGBB value")


class PermissionsDoc(_StrictCollectionDocBase):
    """Versioned permission identifier with catalog category and descriptive metadata."""

    permission_id: str
    label: str
    category: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    system_managed: bool = factory_value("records.system_managed")
    is_active: bool = factory_value("records.is_active")
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, value: Any) -> str:
        """Require an exact configured permission category after trimming.

        Args:
            value: Category label; matching remains case-sensitive.

        Returns:
            The stripped category label.

        Raises:
            ValueError: If the label is not in the permission catalog.
        """
        return normalize_permission_category(value)

    @field_validator("permission_id", mode="before")
    @classmethod
    def _normalize_permission_id(cls, value: Any) -> str:
        """Canonicalize a colon-separated permission identifier.

        Args:
            value: Resource and action, with optional further scope segments.

        Returns:
            The stripped, lowercase identifier.

        Raises:
            ValueError: If blank or not colon-separated nonempty segments containing
                lowercase letters, digits, underscores, or dots.
        """
        permission_id = str(value or "").strip().lower()
        if not permission_id:
            raise ValueError("permission_id is required")
        if not re.fullmatch(r"[a-z0-9_.]+:[a-z0-9_.]+(?::[a-z0-9_.]+)*", permission_id):
            raise ValueError("permission_id must use resource:action[:scope] format")
        return permission_id


def _normalize_permission_ids(value: Any) -> list[str]:
    """Strip, lowercase, and deduplicate permission identifiers.

    Args:
        value: Identifier or iterable; None produces an empty list.

    Returns:
        Nonblank identifiers in first-occurrence order without checking their syntax.
    """
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
