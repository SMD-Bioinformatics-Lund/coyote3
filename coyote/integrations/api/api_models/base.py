"""Shared model primitives for web API payload typing."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="allow")


JsonDict = dict[str, Any]


class ApiMutationResultPayload(ApiModel):
    status: str = "ok"
    action: str
    resource: str
    resource_id: str
    sample_id: str
    meta: JsonDict = Field(default_factory=dict)
