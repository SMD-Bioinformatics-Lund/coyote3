"""Coverage payload models used by Flask coverage blueprint routes."""

from pydantic import Field

from coyote.web_api.api_models.base import ApiModel, JsonDict


class ApiCoverageSamplePayload(ApiModel):
    coverage: JsonDict = Field(default_factory=dict)
    cov_cutoff: int = 500
    sample: JsonDict = Field(default_factory=dict)
    genelists: list[str] = Field(default_factory=list)
    smp_grp: str = "unknown"
    cov_table: JsonDict = Field(default_factory=dict)


class ApiCoverageBlacklistedPayload(ApiModel):
    blacklisted: JsonDict = Field(default_factory=dict)
    group: str = ""

