"""Admin-focused web API payload models."""

from __future__ import annotations

from pydantic import Field

from coyote_web.api_models.base import ApiModel, JsonDict


class ApiAdminRolesPayload(ApiModel):
    roles: list[JsonDict] = Field(default_factory=list)


class ApiAdminRoleCreateContextPayload(ApiModel):
    schemas: list[JsonDict] = Field(default_factory=list)
    selected_schema: JsonDict = Field(default_factory=dict)
    schema: JsonDict = Field(default_factory=dict)


class ApiAdminRoleContextPayload(ApiModel):
    role: JsonDict = Field(default_factory=dict)
    schema: JsonDict = Field(default_factory=dict)

