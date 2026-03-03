"""Admin route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminRolesListPayload(BaseModel):
    roles: list[dict[str, Any]]


class AdminRoleCreateContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminRoleContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminUsersListPayload(BaseModel):
    users: list[dict[str, Any]]
    roles: dict[str, Any]


class AdminUserCreateContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")
    role_map: dict[str, Any]
    assay_group_map: dict[str, list[dict[str, Any]]]


class AdminUserContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_doc: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")
    role_map: dict[str, Any]
    assay_group_map: dict[str, list[dict[str, Any]]]


class AdminPermissionsListPayload(BaseModel):
    permission_policies: list[dict[str, Any]]
    grouped_permissions: dict[str, list[dict[str, Any]]]


class AdminPermissionCreateContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminPermissionContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    permission: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminMutationPayload(BaseModel):
    status: str
    sample_id: str
    resource: str
    resource_id: str
    action: str
    meta: dict[str, Any]


class AdminPanelsListPayload(BaseModel):
    panels: list[dict[str, Any]]


class AdminPanelContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    panel: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminPanelCreateContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminGenelistsListPayload(BaseModel):
    genelists: list[dict[str, Any]]


class AdminGenelistCreateContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")
    assay_group_map: dict[str, list[dict[str, Any]]]


class AdminGenelistContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    genelist: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")
    assay_group_map: dict[str, list[dict[str, Any]]]


class AdminGenelistViewContextPayload(BaseModel):
    genelist: dict[str, Any]
    selected_assay: str | None = None
    filtered_genes: list[str]
    panel_germline_genes: list[str]


class AdminAspcListPayload(BaseModel):
    assay_configs: list[dict[str, Any]]


class AdminAspcCreateContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category: str
    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")
    prefill_map: dict[str, dict[str, Any]]


class AdminAspcContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assay_config: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminSchemasListPayload(BaseModel):
    schemas: list[dict[str, Any]]


class AdminSchemaContextPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_payload: dict[str, Any] = Field(alias="schema")
