# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Validated account-operation inputs shared by trusted hosts and HTTP validation."""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, Field

from coyote.config.factory_defaults import factory_value


class SessionActivitySummary(BaseModel):
    """Aggregate valid login sessions without exposing identities or credentials."""

    signed_in_users: int = Field(ge=0)
    active_sessions: int = Field(ge=0)
    recently_active_users: int = Field(ge=0)
    recent_activity_seconds: int = Field(gt=0)
    observed_at: AwareDatetime


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
    table_page_size: int | None = Field(
        default=None, ge=1, le=factory_value("pagination.max_page_size")
    )
    theme: str | None = Field(default=None, pattern="^(auto|light|dark)$")


class ApiPasswordResetConfirmRequest(BaseModel):
    """Represent a password reset confirm payload."""

    token: str
    new_password: str
