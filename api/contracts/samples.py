"""Sample and coverage-mutation route contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SampleCommentCreateRequest(BaseModel):
    """Represent the sample comment create request payload."""

    form_data: dict[str, Any] = Field(default_factory=dict)


class SampleCommentSuggestionPayload(BaseModel):
    """Represent generated text available to the sample comment editor."""

    sample_id: str
    sample_name: str
    analysis: str
    suggested_text: str


class SampleFiltersUpdateRequest(BaseModel):
    """Represent the sample filters update request payload."""

    filters: dict[str, Any]


class CoverageBlacklistUpdateRequest(BaseModel):
    """Represent the coverage blacklist update request payload."""

    gene: str
    smp_grp: str
    region: str
    coord: str | None = None
    status: str | None = None


class SampleChangePayload(BaseModel):
    """Represent the sample change payload."""

    status: str
    sample_id: str
    resource: str
    resource_id: str
    action: str
    meta: dict[str, Any]


class SampleBamFilesPayload(BaseModel):
    """Represent BAM-service file mappings for a resolved sample."""

    query: dict[str, Any]
    sample: dict[str, Any]
    bam_files: dict[str, list[str]] = Field(default_factory=dict)


class CoverageBlacklistStatusPayload(BaseModel):
    """Represent the coverage blacklist status payload."""

    status: str
    message: str
