"""System and authentication route contracts."""

from __future__ import annotations

from pydantic import BaseModel


class HealthPayload(BaseModel):
    """Represent the health payload."""

    status: str


class WhoamiPayload(BaseModel):
    """Represent the whoami payload."""

    username: str
    firstname: str = ""
    fullname: str = ""
    roles: list[str]
    role: str
    access_level: int
    permissions: list[str]
    ui_settings: dict[str, str | bool | int]
    csrf_token: str


class AuthUserEnvelope(BaseModel):
    """Provide the auth user envelope type."""

    status: str
    user: dict


class AuthLoginEnvelope(AuthUserEnvelope):
    """Provide the auth login envelope type."""

    csrf_token: str
