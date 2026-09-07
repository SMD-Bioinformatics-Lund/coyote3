"""Configurable genelist router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from api.app.container import util
from api.app.deps.services import get_admin_genelist_service
from api.application.resources.isgl import IsglService
from api.contracts.admin import (
    AdminChangePayload,
    AdminExistsPayload,
    AdminGenelistContextPayload,
    AdminGenelistCreateContextPayload,
    AdminGenelistsListPayload,
    AdminGenelistViewContextPayload,
)
from api.interfaces.http.admin.resources.audit import set_managed_resource_audit_context
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_ADMIN_ASSAYS])


@router.post(
    "/api/v1/resources/genelists",
    response_model=AdminChangePayload,
    status_code=201,
    summary="Create genelist",
)
def create_genelist_change(
    request: Request,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:create")),
    service: IsglService = Depends(get_admin_genelist_service),
):
    """Create a genelist.

    Args:
        payload: Submitted genelist payload.
        user: Authenticated user performing the mutation.
        service: Genelist workflow service.

    Returns:
        dict: Mutation response payload.
    """
    result = service.create(payload=payload, actor_username=user.username)
    set_managed_resource_audit_context(
        request, resource_type="genelist", action="created", result=result
    )
    return util.common.convert_to_serializable(result)


@router.get("/api/v1/resources/genelists", response_model=AdminGenelistsListPayload)
def list_genelists_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:list")),
    service: IsglService = Depends(get_admin_genelist_service),
):
    """Return the genelist admin list.

    Args:
        user: Authenticated user requesting the list.
        service: Genelist workflow service.

    Returns:
        dict: Admin list payload for genelists.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.list_payload(q=q, page=page, per_page=per_page)
    )


@router.get(
    "/api/v1/resources/genelists/create_context", response_model=AdminGenelistCreateContextPayload
)
def create_genelist_context_read(
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:create")),
    service: IsglService = Depends(get_admin_genelist_service),
):
    """Return create-form context for a genelist.

    Args:
        user: Authenticated user requesting create context.
        service: Genelist workflow service.

    Returns:
        dict: Create-context payload for genelists.
    """
    return util.common.convert_to_serializable(
        service.create_context_payload(actor_username=user.username)
    )


@router.get(
    "/api/v1/resources/genelists/{genelist_id}/context", response_model=AdminGenelistContextPayload
)
def genelist_context_read(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:view")),
    service: IsglService = Depends(get_admin_genelist_service),
):
    """Return edit-form context for a genelist.

    Args:
        genelist_id: Genelist identifier to load.
        user: Authenticated user requesting edit context.
        service: Genelist workflow service.

    Returns:
        dict: Edit-context payload for the genelist.
    """
    _ = user
    return util.common.convert_to_serializable(service.context_payload(genelist_id=genelist_id))


@router.get(
    "/api/v1/resources/genelists/{genelist_id}/view_context",
    response_model=AdminGenelistViewContextPayload,
)
def genelist_view_context_read(
    genelist_id: str,
    assay: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:view")),
    service: IsglService = Depends(get_admin_genelist_service),
):
    """Return read-only context for a genelist.

    Args:
        genelist_id: Genelist identifier to load.
        assay: Optional assay used to filter visible genes.
        user: Authenticated user requesting the view context.
        service: Genelist workflow service.

    Returns:
        dict: View-context payload for the genelist.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.view_context_payload(genelist_id=genelist_id, assay=assay)
    )


@router.put(
    "/api/v1/resources/genelists/{genelist_id}",
    response_model=AdminChangePayload,
    summary="Update genelist",
)
def update_genelist_change(
    request: Request,
    genelist_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:edit")),
    service: IsglService = Depends(get_admin_genelist_service),
):
    """Update a genelist.

    Args:
        genelist_id: Genelist identifier to update.
        payload: Submitted genelist payload.
        user: Authenticated user performing the mutation.
        service: Genelist workflow service.

    Returns:
        dict: Mutation response payload.
    """
    result = service.update(
        genelist_id=genelist_id,
        payload=payload,
        actor_username=user.username,
    )
    set_managed_resource_audit_context(
        request, resource_type="genelist", action="updated", result=result
    )
    return util.common.convert_to_serializable(result)


@router.patch(
    "/api/v1/resources/genelists/{genelist_id}/status",
    response_model=AdminChangePayload,
    summary="Toggle genelist status",
)
def toggle_genelist_change(
    request: Request,
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:edit")),
    service: IsglService = Depends(get_admin_genelist_service),
):
    """Toggle genelist active status.

    Args:
        genelist_id: Genelist identifier to toggle.
        user: Authenticated user performing the mutation.
        service: Genelist workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    result = service.toggle(genelist_id=genelist_id)
    set_managed_resource_audit_context(
        request, resource_type="genelist", action="updated", result=result
    )
    return util.common.convert_to_serializable(result)


@router.delete(
    "/api/v1/resources/genelists/{genelist_id}",
    response_model=AdminChangePayload,
    summary="Delete genelist",
)
def delete_genelist_change(
    request: Request,
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:delete")),
    service: IsglService = Depends(get_admin_genelist_service),
):
    """Delete a genelist.

    Args:
        genelist_id: Genelist identifier to delete.
        user: Authenticated user performing the mutation.
        service: Genelist workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    result = service.delete(genelist_id=genelist_id)
    set_managed_resource_audit_context(
        request, resource_type="genelist", action="deleted", result=result
    )
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/resources/genelists/validate_isgl_id", response_model=AdminExistsPayload)
def validate_isgl_id_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:create")),
    service: IsglService = Depends(get_admin_genelist_service),
):
    """Validate whether an isgl_id already exists."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.genelist_exists(isgl_id=str(payload.get("isgl_id", "")))}
    )
