"""Authentication API contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from api.config.constants import TABLE_PAGE_SIZE_OPTIONS


class ApiAuthLoginRequest(BaseModel):
    """Represent the api auth login request payload."""

    username: str
    password: str
    provider: str


class ApiAuthProvidersResponse(BaseModel):
    """Represent enabled authentication providers for the login client."""

    providers: list[str]


class ApiAvailabilityResponse(BaseModel):
    """Represent the api availability response payload."""

    exists: bool


class ApiSessionDeleteResponse(BaseModel):
    """Represent the api session delete response payload."""

    status: str = Field(default="ok")


class ApiStatusResponse(BaseModel):
    """Represent a simple successful API status response."""

    status: str = Field(default="ok")


class ApiPasswordChangeResponse(ApiStatusResponse):
    """Represent a successful password change response."""

    username: str


class ApiAuthWhoAmIResponse(BaseModel):
    """Represent the api auth who am i response payload."""

    username: str
    roles: list[str]
    role: str
    access_level: int
    permissions: list[str]


class ApiPasswordChangeRequest(BaseModel):
    """Represent an authenticated local password change request."""

    current_password: str
    new_password: str


class ApiProfileUpdateRequest(BaseModel):
    """Safe identity fields an authenticated user may edit on their own account."""

    firstname: str = Field(max_length=120)
    lastname: str = Field(max_length=120)
    fullname: str = Field(max_length=240)
    job_title: str = Field(max_length=160)


class ApiProfileUpdateResponse(ApiStatusResponse):
    """Updated current-user profile."""

    user: dict


class ApiUiSettingsUpdateRequest(BaseModel):
    """Validated presentation preferences for the authenticated user."""

    analysis_layout: str | None = Field(default=None, pattern="^(classic|modern)$")
    sample_list_layout: str | None = Field(default=None, pattern="^(classic|modern)$")
    analysis_modern_view_tried: bool | None = None
    sample_list_modern_view_tried: bool | None = None
    table_page_size: int | None = None

    @field_validator("table_page_size")
    @classmethod
    def _validate_table_page_size(cls, value: int | None) -> int | None:
        if value is not None and value not in TABLE_PAGE_SIZE_OPTIONS:
            allowed = ", ".join(str(option) for option in TABLE_PAGE_SIZE_OPTIONS)
            raise ValueError(f"table_page_size must be one of: {allowed}")
        return value


class ApiUiSettingsUpdateResponse(ApiStatusResponse):
    """Updated current-user presentation preferences."""

    ui_settings: dict[str, str | bool | int]


class ApiPasswordResetRequest(BaseModel):
    """Represent a password reset request payload."""

    username: str


class ApiPasswordResetConfirmRequest(BaseModel):
    """Represent a password reset confirm payload."""

    token: str
    new_password: str
