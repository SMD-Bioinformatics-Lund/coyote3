"""Admin route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminListPagePayload(BaseModel):
    """Represent shared pagination metadata for admin list responses."""

    q: str = ""
    page: int = 1
    per_page: int = 30
    total: int = 0
    has_next: bool = False


class AdminRolesListPayload(BaseModel):
    """Represent the admin roles list payload."""

    roles: list[dict[str, Any]]
    pagination: AdminListPagePayload


class AdminRoleCreateContextPayload(BaseModel):
    """Represent the admin role create context payload."""

    model_config = ConfigDict(populate_by_name=True)

    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminRoleContextPayload(BaseModel):
    """Represent the admin role context payload."""

    model_config = ConfigDict(populate_by_name=True)

    role: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminUsersListPayload(BaseModel):
    """Represent the admin users list payload."""

    users: list[dict[str, Any]]
    roles: dict[str, Any]
    pagination: AdminListPagePayload


class AdminUserCreateContextPayload(BaseModel):
    """Represent the admin user create context payload."""

    model_config = ConfigDict(populate_by_name=True)

    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")
    role_map: dict[str, Any]
    assay_group_map: dict[str, list[dict[str, Any]]]


class AdminUserContextPayload(BaseModel):
    """Represent the admin user context payload."""

    model_config = ConfigDict(populate_by_name=True)

    user_doc: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")
    role_map: dict[str, Any]
    assay_group_map: dict[str, list[dict[str, Any]]]


class AdminPermissionsListPayload(BaseModel):
    """Represent the admin permissions list payload."""

    permission_policies: list[dict[str, Any]]
    grouped_permissions: dict[str, list[dict[str, Any]]]
    pagination: AdminListPagePayload


class AdminPermissionCreateContextPayload(BaseModel):
    """Represent the admin permission create context payload."""

    model_config = ConfigDict(populate_by_name=True)

    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminPermissionContextPayload(BaseModel):
    """Represent the admin permission context payload."""

    model_config = ConfigDict(populate_by_name=True)

    permission: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminMutationPayload(BaseModel):
    """Represent the admin mutation payload."""

    status: str
    sample_id: str
    resource: str
    resource_id: str
    action: str
    meta: dict[str, Any]


class AdminPanelsListPayload(BaseModel):
    """Represent the admin panels list payload."""

    panels: list[dict[str, Any]]
    pagination: AdminListPagePayload


class AdminPanelContextPayload(BaseModel):
    """Represent the admin panel context payload."""

    model_config = ConfigDict(populate_by_name=True)

    panel: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminPanelCreateContextPayload(BaseModel):
    """Represent the admin panel create context payload."""

    model_config = ConfigDict(populate_by_name=True)

    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")


class AdminGenelistsListPayload(BaseModel):
    """Represent the admin genelists list payload."""

    genelists: list[dict[str, Any]]
    pagination: AdminListPagePayload


class AdminGenelistCreateContextPayload(BaseModel):
    """Represent the admin genelist create context payload."""

    model_config = ConfigDict(populate_by_name=True)

    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")
    assay_group_map: dict[str, list[dict[str, Any]]]


class AdminGenelistContextPayload(BaseModel):
    """Represent the admin genelist context payload."""

    model_config = ConfigDict(populate_by_name=True)

    genelist: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")
    assay_group_map: dict[str, list[dict[str, Any]]]


class AdminGenelistViewContextPayload(BaseModel):
    """Represent the admin genelist view context payload."""

    genelist: dict[str, Any]
    selected_assay: str | None = None
    filtered_genes: list[str]
    panel_germline_genes: list[str]


class AdminAspcListPayload(BaseModel):
    """Represent the admin aspc list payload."""

    assay_configs: list[dict[str, Any]]
    pagination: AdminListPagePayload


class AdminAspcCreateContextPayload(BaseModel):
    """Represent the admin aspc create context payload."""

    model_config = ConfigDict(populate_by_name=True)

    category: str
    schemas: list[dict[str, Any]]
    selected_schema: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")
    prefill_map: dict[str, dict[str, Any]]
    query_profile_options: dict[str, list[str]] | None = None


class AdminAspcContextPayload(BaseModel):
    """Represent the admin aspc context payload."""

    model_config = ConfigDict(populate_by_name=True)

    assay_config: dict[str, Any]
    schema_payload: dict[str, Any] = Field(alias="schema")
    query_profile_options: dict[str, list[str]] | None = None


class AdminQueryProfileOptionsPayload(BaseModel):
    """Represent filtered query-profile options for ASPC form dropdowns."""

    options: dict[str, list[str]]


class AdminExistsPayload(BaseModel):
    """Represent the admin exists payload."""

    exists: bool


class AdminSamplesListPayload(BaseModel):
    """Represent the admin samples list payload."""

    samples: list[dict[str, Any]]
    pagination: AdminListPagePayload


class AdminSampleContextPayload(BaseModel):
    """Represent the admin sample context payload."""

    sample: dict[str, Any]
