"""Internal payload models used for server-to-server web calls."""

from pydantic import Field

from coyote.integrations.api.api_models.base import ApiModel


class ApiInternalIsglMetaPayload(ApiModel):
    status: str = "ok"
    isgl_id: str
    is_adhoc: bool = False
    display_name: str = Field(default="")


class ApiInternalRoleLevelsPayload(ApiModel):
    status: str = "ok"
    role_levels: dict[str, int] = Field(default_factory=dict)
