"""Configurable genelist router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from api.app.container import util
from api.app.deps.application import get_gene_lists, get_reference_data
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.interfaces.http.v1.admin.resources.audit import set_managed_resource_audit_context
from api.security.access import ApiUser, require_access
from coyote3.application.operations.administration import GeneLists, ReferenceData
from coyote3.contracts.admin import (
    AdminChangePayload,
    AdminExistsPayload,
    AdminGenelistContextPayload,
    AdminGenelistCreateContextPayload,
    AdminGenelistsListPayload,
    AdminGenelistViewContextPayload,
)
from coyote3.contracts.resource_fields import FieldValue, GeneListField
from coyote3.contracts.resource_metadata import GeneListMetadata

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
    service: GeneLists = Depends(get_gene_lists),
):
    """Create a genelist.

    \u000c

    Args:
        request: Request receiving audit metadata for the created genelist.
        payload: Submitted genelist payload.
        user: Authenticated user performing the mutation.
        service: Genelist workflow service.

    Returns:
        dict: Mutation response payload.
    """
    result = service.create_genelist(payload=payload)
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
    service: GeneLists = Depends(get_gene_lists),
):
    """Return the genelist admin list.

    \u000c

    Args:
        q: Case-insensitive text search across genelist identifiers and metadata;
            blank text omits the search filter.
        page: One-based result page; defaults to 1.
        per_page: Page size from 1 to 200; defaults to 30.
        user: Authenticated user requesting the list.
        service: Genelist workflow service.

    Returns:
        dict: Admin list payload for genelists.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.list_genelists(q=q, page=page, per_page=per_page)
    )


@router.get(
    "/api/v1/resources/genelists/create_context", response_model=AdminGenelistCreateContextPayload
)
def create_genelist_context_read(
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:create")),
    service: GeneLists = Depends(get_gene_lists),
):
    """Return create-form context for a genelist.

    \u000c

    Args:
        user: Authenticated user requesting create context.
        service: Genelist workflow service.

    Returns:
        dict: Create-context payload for genelists.
    """
    return util.common.convert_to_serializable(service.create_genelist_context())


@router.get("/api/v1/resources/genelists/{genelist_id}/metadata", response_model=GeneListMetadata)
def genelist_metadata_read(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:view")),
    service: ReferenceData = Depends(get_reference_data),
):
    """Return permitted gene-list metadata; requires gene_list.insilico:view."""
    return service.gene_list_metadata(genelist_id)


@router.get(
    "/api/v1/resources/genelists/{genelist_id}/fields/{field}",
    response_model=FieldValue,
)
def genelist_field_read(
    genelist_id: str,
    field: GeneListField,
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:view")),
    service: ReferenceData = Depends(get_reference_data),
):
    """Return one gene-list value; requires gene_list.insilico:view."""
    _ = user
    return util.common.convert_to_serializable(service.gene_list_field(genelist_id, field))


@router.get(
    "/api/v1/resources/genelists/{genelist_id}/context", response_model=AdminGenelistContextPayload
)
def genelist_context_read(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:view")),
    service: GeneLists = Depends(get_gene_lists),
):
    """Return edit-form context for a genelist.

    \u000c

    Args:
        genelist_id: Genelist identifier to load.
        user: Authenticated user requesting edit context.
        service: Genelist workflow service.

    Returns:
        dict: Edit-context payload for the genelist.
    """
    _ = user
    return util.common.convert_to_serializable(service.genelist_context(genelist_id=genelist_id))


@router.get(
    "/api/v1/resources/genelists/{genelist_id}/view_context",
    response_model=AdminGenelistViewContextPayload,
)
def genelist_view_context_read(
    genelist_id: str,
    assay: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:view")),
    service: GeneLists = Depends(get_gene_lists),
):
    """Return read-only context for a genelist.

    \u000c

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
        service.genelist_view_context(genelist_id=genelist_id, assay=assay)
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
    service: GeneLists = Depends(get_gene_lists),
):
    """Update a genelist.

    \u000c

    Args:
        request: Request receiving audit metadata for the updated genelist.
        genelist_id: Genelist identifier to update.
        payload: Submitted genelist payload.
        user: Authenticated user performing the mutation.
        service: Genelist workflow service.

    Returns:
        dict: Mutation response payload.
    """
    result = service.update_genelist(genelist_id=genelist_id, payload=payload)
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
    service: GeneLists = Depends(get_gene_lists),
):
    """Toggle genelist active status.

    \u000c

    Args:
        request: Request receiving audit metadata for the genelist status change.
        genelist_id: Genelist identifier to toggle.
        user: Authenticated user performing the mutation.
        service: Genelist workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    result = service.toggle_genelist(genelist_id=genelist_id)
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
    service: GeneLists = Depends(get_gene_lists),
):
    """Delete a genelist.

    \u000c

    Args:
        request: Request receiving audit metadata for the deleted genelist.
        genelist_id: Genelist identifier to delete.
        user: Authenticated user performing the mutation.
        service: Genelist workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    result = service.delete_genelist(genelist_id=genelist_id)
    set_managed_resource_audit_context(
        request, resource_type="genelist", action="deleted", result=result
    )
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/resources/genelists/validate_isgl_id", response_model=AdminExistsPayload)
def validate_isgl_id_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="gene_list.insilico:create")),
    service: GeneLists = Depends(get_gene_lists),
):
    """Validate whether an isgl_id already exists."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.validate_isgl_id(payload=payload)}
    )
