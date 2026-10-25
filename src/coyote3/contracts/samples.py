"""Sample and coverage-mutation route contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConfigurationApplyRequest(BaseModel):
    """Apply only the configuration and sample state reviewed in the preceding preview."""

    expected_version: int = Field(ge=1)
    configuration_id: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2000)
    retain_overrides: bool = False


class ConfigurationPreviewPayload(BaseModel):
    """Reviewed candidate, effective filter changes and optimistic concurrency preconditions."""

    expected_version: int = Field(ge=1)
    configuration_id: str = Field(min_length=1)
    configuration: dict[str, Any]
    filters_before: dict[str, Any] | None
    filters_after: dict[str, Any]
    retain_overrides: bool
    changed_components: list[
        Literal[
            "assay_resource_release",
            "gene_list_release",
            "query_policy_release",
            "clinical_rule_release",
        ]
    ]


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
