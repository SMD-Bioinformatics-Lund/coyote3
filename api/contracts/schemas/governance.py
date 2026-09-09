"""Access-control and schema-definition contracts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.config.constants import (
    DEFAULT_AUTH_PROVIDER,
    DEFAULT_TABLE_PAGE_SIZE,
    TABLE_PAGE_SIZE_OPTIONS,
    normalize_asp_group,
    normalize_auth_types,
    normalize_environment,
    normalize_permission_category,
)
from api.contracts.schemas.base import _StrictCollectionDocBase


class UserUiSettingsDoc(BaseModel):
    """Persisted presentation preferences for one user."""

    model_config = ConfigDict(extra="forbid")

    analysis_layout: str = "classic"
    sample_list_layout: str = "classic"
    analysis_modern_view_tried: bool = False
    sample_list_modern_view_tried: bool = False
    table_page_size: int = DEFAULT_TABLE_PAGE_SIZE

    @field_validator("analysis_layout")
    @classmethod
    def _validate_analysis_layout(cls, value: str) -> str:
        """Normalize a analysis layout preference.

        Args:
            value: Layout name before whitespace and case normalization.

        Returns:
            The lowercase classic or modern layout name.

        Raises:
            ValueError: If the layout is neither classic nor modern.
        """
        normalized = str(value or "").strip().lower()
        if normalized not in {"classic", "modern"}:
            raise ValueError("analysis_layout must be one of: classic, modern")
        return normalized

    @field_validator("sample_list_layout")
    @classmethod
    def _validate_sample_list_layout(cls, value: str) -> str:
        """Normalize a sample-list layout preference.

        Args:
            value: Layout name before whitespace and case normalization.

        Returns:
            The lowercase classic or modern layout name.

        Raises:
            ValueError: If the layout is neither classic nor modern.
        """
        normalized = str(value or "").strip().lower()
        if normalized not in {"classic", "modern"}:
            raise ValueError("sample_list_layout must be one of: classic, modern")
        return normalized

    @field_validator("table_page_size")
    @classmethod
    def _validate_table_page_size(cls, value: int) -> int:
        """Check page size against the supported table-size choices.

        Args:
            value: Requested number of rows per table page.

        Returns:
            The supported page size unchanged.

        Raises:
            ValueError: If the size is absent from TABLE_PAGE_SIZE_OPTIONS.
        """
        if value not in TABLE_PAGE_SIZE_OPTIONS:
            allowed = ", ".join(str(option) for option in TABLE_PAGE_SIZE_OPTIONS)
            raise ValueError(f"table_page_size must be one of: {allowed}")
        return value


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
    system_managed: bool = False
    is_active: bool = True
    version: int = 1
    created_by: str | None = None
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str | None = None
    updated_on: datetime | None = None

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
    system_managed: bool = False
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
        """Accept a six-digit hex color or an existing named-color token.

        Args:
            value: Role color before whitespace and case normalization.

        Returns:
            The stripped, lowercase hex value or named token.

        Raises:
            ValueError: If neither hex syntax nor a letter-led named token is matched.
        """
        normalized = str(value or "").strip().lower()
        if re.fullmatch(r"#[0-9a-f]{6}", normalized):
            return normalized
        # Preserve named colors already stored by earlier releases. New color
        # picker selections are always persisted as explicit hex values.
        if re.fullmatch(r"[a-z][a-z0-9_-]*", normalized):
            return normalized
        raise ValueError("color must be a six-digit #RRGGBB value")


class PermissionsDoc(_StrictCollectionDocBase):
    """Versioned permission identifier with catalog category and descriptive metadata."""

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
