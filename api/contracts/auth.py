"""Authentication API contracts."""

from pydantic import BaseModel


class ApiAuthLoginRequest(BaseModel):
    username: str
    password: str


class ApiAuthWhoAmIResponse(BaseModel):
    username: str
    role: str
    access_level: int
    permissions: list[str]
    denied_permissions: list[str]
