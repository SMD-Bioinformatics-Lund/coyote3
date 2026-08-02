"""Authentication API contracts."""

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


class ApiPasswordResetRequest(BaseModel):
    """Represent a password reset request payload."""

    username: str


class ApiPasswordResetConfirmRequest(BaseModel):
    """Represent a password reset confirm payload."""

    token: str
    new_password: str
