"""Auth payload models used by the Flask web API client."""

from pydantic import Field

from coyote.integrations.api.api_models.base import ApiModel, JsonDict


class ApiAuthLoginPayload(ApiModel):
    status: str = "ok"
    user: JsonDict = Field(default_factory=dict)
    session_token: str = ""


class ApiAuthSessionUserPayload(ApiModel):
    status: str = "ok"
    user: JsonDict = Field(default_factory=dict)


class ApiAuthMePayload(ApiModel):
    status: str = "ok"
    user: JsonDict = Field(default_factory=dict)
