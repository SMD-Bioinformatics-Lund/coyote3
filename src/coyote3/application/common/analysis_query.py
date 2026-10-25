"""Transport-independent inputs for filtered and paginated finding reads."""

from pydantic import BaseModel, ConfigDict, Field


class AnalysisQuery(BaseModel):
    """Carry explicit query values and optional origin metadata into application services."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    parameters: dict[str, str] = Field(default_factory=dict)
    source_path: str = ""
