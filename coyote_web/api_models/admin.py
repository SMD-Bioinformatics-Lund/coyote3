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


class ApiAdminPermissionsPayload(ApiModel):
    permission_policies: list[JsonDict] = Field(default_factory=list)
    grouped_permissions: JsonDict = Field(default_factory=dict)


class ApiAdminPermissionCreateContextPayload(ApiModel):
    schemas: list[JsonDict] = Field(default_factory=list)
    selected_schema: JsonDict = Field(default_factory=dict)
    schema: JsonDict = Field(default_factory=dict)


class ApiAdminPermissionContextPayload(ApiModel):
    permission: JsonDict = Field(default_factory=dict)
    schema: JsonDict = Field(default_factory=dict)


class ApiAdminUsersPayload(ApiModel):
    users: list[JsonDict] = Field(default_factory=list)
    roles: JsonDict = Field(default_factory=dict)


class ApiAdminUserCreateContextPayload(ApiModel):
    schemas: list[JsonDict] = Field(default_factory=list)
    selected_schema: JsonDict = Field(default_factory=dict)
    schema: JsonDict = Field(default_factory=dict)
    role_map: JsonDict = Field(default_factory=dict)
    assay_group_map: JsonDict = Field(default_factory=dict)


class ApiAdminUserContextPayload(ApiModel):
    user_doc: JsonDict = Field(default_factory=dict)
    schema: JsonDict = Field(default_factory=dict)
    role_map: JsonDict = Field(default_factory=dict)
    assay_group_map: JsonDict = Field(default_factory=dict)


class ApiAdminSchemasPayload(ApiModel):
    schemas: list[JsonDict] = Field(default_factory=list)


class ApiAdminSchemaContextPayload(ApiModel):
    schema: JsonDict = Field(default_factory=dict)
