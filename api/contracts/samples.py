"""Sample and coverage-mutation route contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SampleCommentCreateRequest(BaseModel):
    form_data: dict[str, Any] = Field(default_factory=dict)


class SampleFiltersUpdateRequest(BaseModel):
    filters: dict[str, Any]


class CoverageBlacklistUpdateRequest(BaseModel):
    gene: str
    smp_grp: str
    region: str
    coord: str | None = None
    status: str | None = None


class SampleMutationPayload(BaseModel):
    status: str
    sample_id: str
    resource: str
    resource_id: str
    action: str
    meta: dict[str, Any]


class CoverageBlacklistStatusPayload(BaseModel):
    status: str
    message: str
