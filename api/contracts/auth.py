"""Authentication API contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApiAuthLoginRequest(BaseModel):
    """Represent the api auth login request payload.
    """
    username: str
    password: str


class ApiAvailabilityResponse(BaseModel):
    """Represent the api availability response payload.
    """
    exists: bool


class ApiSessionDeleteResponse(BaseModel):
    """Represent the api session delete response payload.
    """
    status: str = Field(default="ok")


class ApiAuthWhoAmIResponse(BaseModel):
    """Represent the api auth who am i response payload.
    """
    username: str
    role: str
    access_level: int
    permissions: list[str]
    denied_permissions: list[str]
