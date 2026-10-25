"""Validated account-operation inputs shared by trusted hosts and HTTP validation."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from coyote3.config.constants import TABLE_PAGE_SIZE_OPTIONS


class ApiPasswordChangeRequest(BaseModel):
    """Represent an authenticated local password change request."""

    current_password: str
    new_password: str
    confirm_password: str | None = None


class ApiProfileUpdateRequest(BaseModel):
    """Safe identity fields an authenticated user may edit on their own account."""

    firstname: str = Field(max_length=120)
    lastname: str = Field(max_length=120)
    fullname: str = Field(max_length=240)
    job_title: str = Field(max_length=160)


class ApiUiSettingsUpdateRequest(BaseModel):
    """Validated presentation preferences for the authenticated user."""

    analysis_layout: str | None = Field(default=None, pattern="^(classic|modern)$")
    sample_list_layout: str | None = Field(default=None, pattern="^(classic|modern)$")
    analysis_modern_view_tried: bool | None = None
    sample_list_modern_view_tried: bool | None = None
    table_page_size: int | None = None
    theme: str | None = Field(default=None, pattern="^(auto|light|dark)$")

    @field_validator("table_page_size")
    @classmethod
    def _validate_table_page_size(cls, value: int | None) -> int | None:
        """Validate an optional table page-size preference.

        Args:
            value: Rows per page, or None when the update does not specify a size.

        Returns:
            The supported size unchanged, including None.

        Raises:
            ValueError: If a nonnull size is absent from TABLE_PAGE_SIZE_OPTIONS.
        """
        if value is not None and value not in TABLE_PAGE_SIZE_OPTIONS:
            allowed = ", ".join(str(option) for option in TABLE_PAGE_SIZE_OPTIONS)
            raise ValueError(f"table_page_size must be one of: {allowed}")
        return value


class ApiPasswordResetConfirmRequest(BaseModel):
    """Represent a password reset confirm payload."""

    token: str
    new_password: str
