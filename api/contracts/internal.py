"""Internal API route contracts."""

from __future__ import annotations

from pydantic import BaseModel


class RoleLevelsPayload(BaseModel):
    status: str
    role_levels: dict[str, int]


class IsglMetaPayload(BaseModel):
    status: str
    isgl_id: str
    is_adhoc: bool
    display_name: str | None = None
