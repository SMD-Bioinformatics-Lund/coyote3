"""Internal payload models used for server-to-server web calls."""

from pydantic import Field

from coyote.integrations.api.api_models.base import ApiModel


class ApiInternalIsglMetaPayload(ApiModel):
    status: str = "ok"
    isgl_id: str
    is_adhoc: bool = False
    display_name: str = Field(default="")


class ApiInternalSampleAccessPayload(ApiModel):
    status: str = "ok"
    sample_ref: str
    sample_assay: str = ""
    allowed: bool = False
    sample: dict = Field(default_factory=dict)
