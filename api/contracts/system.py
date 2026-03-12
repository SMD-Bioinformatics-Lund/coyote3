"""System and authentication route contracts."""

from __future__ import annotations

from pydantic import BaseModel


class HealthPayload(BaseModel):
    status: str


class WhoamiPayload(BaseModel):
    username: str
    role: str
    access_level: int
    permissions: list[str]
    denied_permissions: list[str]


class AuthUserEnvelope(BaseModel):
    status: str
    user: dict


class AuthLoginEnvelope(AuthUserEnvelope):
    pass
