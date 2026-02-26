"""Shared model primitives for web API payload typing."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="allow")


JsonDict = dict[str, Any]
