"""HTTP authentication requests and session response envelopes."""

from __future__ import annotations

from pydantic import BaseModel, Field


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


class ApiProfileUpdateResponse(ApiStatusResponse):
    """Updated current-user profile."""

    user: dict


class ApiUiSettingsUpdateResponse(ApiStatusResponse):
    """Updated current-user presentation preferences."""

    ui_settings: dict[str, str | bool | int]


class ApiPasswordResetRequest(BaseModel):
    """Represent a password reset request payload."""

    username: str
