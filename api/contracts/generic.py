"""Generic permissive route contract for incremental migration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GenericPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
