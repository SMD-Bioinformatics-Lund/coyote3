"""Sample and coverage-mutation route contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SampleCommentCreateRequest(BaseModel):
    """Represent the sample comment create request payload.
    """
    form_data: dict[str, Any] = Field(default_factory=dict)


class SampleFiltersUpdateRequest(BaseModel):
    """Represent the sample filters update request payload.
    """
    filters: dict[str, Any]


class CoverageBlacklistUpdateRequest(BaseModel):
    """Represent the coverage blacklist update request payload.
    """
    gene: str
    smp_grp: str
    region: str
    coord: str | None = None
    status: str | None = None


class SampleMutationPayload(BaseModel):
    """Represent the sample mutation payload.
    """
    status: str
    sample_id: str
    resource: str
    resource_id: str
    action: str
    meta: dict[str, Any]


class CoverageBlacklistStatusPayload(BaseModel):
    """Represent the coverage blacklist status payload.
    """
    status: str
    message: str
