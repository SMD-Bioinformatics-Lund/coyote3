"""Admin-focused web API payload models."""

from __future__ import annotations

from pydantic import Field

from coyote.integrations.api.api_models.base import ApiModel, JsonDict


class ApiAdminRolesPayload(ApiModel):
    roles: list[JsonDict] = Field(default_factory=list)


class ApiAdminRoleCreateContextPayload(ApiModel):
    schemas: list[JsonDict] = Field(default_factory=list)
    selected_schema: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")


class ApiAdminRoleContextPayload(ApiModel):
    role: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")


class ApiAdminPermissionsPayload(ApiModel):
    permission_policies: list[JsonDict] = Field(default_factory=list)
    grouped_permissions: JsonDict = Field(default_factory=dict)


class ApiAdminPermissionCreateContextPayload(ApiModel):
    schemas: list[JsonDict] = Field(default_factory=list)
    selected_schema: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")


class ApiAdminPermissionContextPayload(ApiModel):
    permission: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")


class ApiAdminUsersPayload(ApiModel):
    users: list[JsonDict] = Field(default_factory=list)
    roles: JsonDict = Field(default_factory=dict)


class ApiAdminUserCreateContextPayload(ApiModel):
    schemas: list[JsonDict] = Field(default_factory=list)
    selected_schema: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")
    role_map: JsonDict = Field(default_factory=dict)
    assay_group_map: JsonDict = Field(default_factory=dict)


class ApiAdminUserContextPayload(ApiModel):
    user_doc: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")
    role_map: JsonDict = Field(default_factory=dict)
    assay_group_map: JsonDict = Field(default_factory=dict)


class ApiAdminSchemasPayload(ApiModel):
    schemas: list[JsonDict] = Field(default_factory=list)


class ApiAdminSchemaContextPayload(ApiModel):
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")


class ApiAdminGenelistsPayload(ApiModel):
    genelists: list[JsonDict] = Field(default_factory=list)


class ApiAdminGenelistCreateContextPayload(ApiModel):
    schemas: list[JsonDict] = Field(default_factory=list)
    selected_schema: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")
    assay_group_map: JsonDict = Field(default_factory=dict)


class ApiAdminGenelistContextPayload(ApiModel):
    genelist: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")
    assay_group_map: JsonDict = Field(default_factory=dict)


class ApiAdminGenelistViewContextPayload(ApiModel):
    genelist: JsonDict = Field(default_factory=dict)
    selected_assay: str | None = None
    filtered_genes: list[str] = Field(default_factory=list)
    panel_germline_genes: list[str] = Field(default_factory=list)


class ApiAdminAspPayload(ApiModel):
    panels: list[JsonDict] = Field(default_factory=list)


class ApiAdminAspCreateContextPayload(ApiModel):
    schemas: list[JsonDict] = Field(default_factory=list)
    selected_schema: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")


class ApiAdminAspContextPayload(ApiModel):
    panel: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")


class ApiAdminAspcPayload(ApiModel):
    assay_configs: list[JsonDict] = Field(default_factory=list)


class ApiAdminAspcCreateContextPayload(ApiModel):
    category: str = "DNA"
    schemas: list[JsonDict] = Field(default_factory=list)
    selected_schema: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")
    prefill_map: JsonDict = Field(default_factory=dict)


class ApiAdminAspcContextPayload(ApiModel):
    assay_config: JsonDict = Field(default_factory=dict)
    schema_payload: JsonDict = Field(default_factory=dict, alias="schema")


class ApiAdminSamplesPayload(ApiModel):
    samples: list[JsonDict] = Field(default_factory=list)


class ApiAdminSampleContextPayload(ApiModel):
    sample: JsonDict = Field(default_factory=dict)
