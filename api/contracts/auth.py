"""Authentication API contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApiAuthLoginRequest(BaseModel):
    username: str
    password: str


class ApiAvailabilityResponse(BaseModel):
    exists: bool


class ApiSessionDeleteResponse(BaseModel):
    status: str = Field(default="ok")


class ApiAuthWhoAmIResponse(BaseModel):
    username: str
    role: str
    access_level: int
    permissions: list[str]
    denied_permissions: list[str]
