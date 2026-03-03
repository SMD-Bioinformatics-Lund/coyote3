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
