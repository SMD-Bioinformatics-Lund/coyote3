"""Configurable genelist router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminGenelistContextPayload,
    AdminGenelistCreateContextPayload,
    AdminGenelistsListPayload,
    AdminGenelistViewContextPayload,
    AdminMutationPayload,
)
from api.deps.services import get_admin_genelist_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.admin_resource_service import AdminGenelistService

router = APIRouter(tags=["resource-genelists"])


@router.post("/api/v1/resources/genelists", response_model=AdminMutationPayload, status_code=201, summary="Create genelist")
def create_genelist_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_isgl", min_role="manager", min_level=99)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.create(payload=payload))


@router.get("/api/v1/resources/genelists", response_model=AdminGenelistsListPayload)
def list_genelists_read(
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.list_payload())


@router.get("/api/v1/resources/genelists/create_context", response_model=AdminGenelistCreateContextPayload)
def create_genelist_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_isgl", min_role="manager", min_level=99)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    return util.common.convert_to_serializable(
        service.create_context_payload(schema_id=schema_id, actor_username=user.username)
    )


@router.get("/api/v1/resources/genelists/{genelist_id}/context", response_model=AdminGenelistContextPayload)
def genelist_context_read(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.context_payload(genelist_id=genelist_id))


@router.get("/api/v1/resources/genelists/{genelist_id}/view_context", response_model=AdminGenelistViewContextPayload)
def genelist_view_context_read(
    genelist_id: str,
    assay: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.view_context_payload(genelist_id=genelist_id, assay=assay))


@router.put("/api/v1/resources/genelists/{genelist_id}", response_model=AdminMutationPayload, summary="Update genelist")
def update_genelist_mutation(
    genelist_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_isgl", min_role="manager", min_level=99)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.update(genelist_id=genelist_id, payload=payload))


@router.patch("/api/v1/resources/genelists/{genelist_id}/status", response_model=AdminMutationPayload, summary="Toggle genelist status")
def toggle_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="edit_isgl", min_role="manager", min_level=99)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.toggle(genelist_id=genelist_id))


@router.delete("/api/v1/resources/genelists/{genelist_id}", response_model=AdminMutationPayload, summary="Delete genelist")
def delete_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="delete_isgl", min_role="admin", min_level=99999)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.delete(genelist_id=genelist_id))
