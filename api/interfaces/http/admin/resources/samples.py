"""Configurable sample resource router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from api.app.container import util
from api.app.deps.services import get_admin_sample_service
from api.application.resources.sample import ResourceSampleService
from api.contracts.admin import (
    AdminChangePayload,
    AdminSampleContextPayload,
    AdminSamplesListPayload,
    AdminSampleUpdatePayload,
)
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_ADMIN_ASSAYS])


@router.get("/api/v1/resources/samples", response_model=AdminSamplesListPayload)
def list_admin_samples_read(
    search: str = Query(default=""),
    asp_group: str = Query(default=""),
    asp_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="sample:list:global")),
    service: ResourceSampleService = Depends(get_admin_sample_service),
):
    """Return the admin sample list.

    Args:
        search: Free-text search string.
        user: Authenticated user requesting the list.
        service: Admin sample workflow service.

    Returns:
        dict: Admin list payload for samples.
    """
    return util.common.convert_to_serializable(
        service.list_payload(
            asp_ids=None if user.is_superuser else user.asp_ids,
            search=search,
            asp_group=asp_group,
            asp_id=asp_id,
            page=page,
            per_page=per_page,
        )
    )


@router.get(
    "/api/v1/resources/samples/{sample_id}/context", response_model=AdminSampleContextPayload
)
def admin_sample_context_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view:global")),
    service: ResourceSampleService = Depends(get_admin_sample_service),
):
    """Return edit context for an admin sample.

    Args:
        sample_id: Sample identifier to load.
        user: Authenticated user requesting edit context.
        service: Admin sample workflow service.

    Returns:
        dict: Edit-context payload for the sample.
    """
    _ = user
    return util.common.convert_to_serializable(service.context_payload(sample_id=sample_id))


@router.put(
    "/api/v1/resources/samples/{sample_id}",
    response_model=AdminChangePayload,
    summary="Update admin sample",
)
def update_sample_change(
    request: Request,
    sample_id: str,
    payload: AdminSampleUpdatePayload = Body(...),
    user: ApiUser = Depends(require_access(permission="sample:edit:global")),
    service: ResourceSampleService = Depends(get_admin_sample_service),
):
    """Update an admin sample.

    Args:
        sample_id: Sample identifier to update.
        payload: Submitted sample payload.
        user: Authenticated user performing the mutation.
        service: Admin sample workflow service.

    Returns:
        dict: Mutation response payload.
    """
    result = service.update(
        sample_id=sample_id,
        payload=payload.model_dump(),
        actor_username=user.username,
    )
    request.state.audit_resource = {
        "type": "sample",
        "id": result.get("meta", {}).get("sample_oid") or result.get("resource_id"),
        "name": result.get("meta", {}).get("sample_name"),
        "message": f"Updated sample {result.get('meta', {}).get('sample_name') or sample_id}",
        "metadata": {
            "sample_oid": result.get("meta", {}).get("sample_oid") or sample_id,
        },
    }
    return util.common.convert_to_serializable(result)


@router.delete(
    "/api/v1/resources/samples/{sample_id}",
    response_model=AdminChangePayload,
    summary="Delete admin sample",
)
def delete_sample_change(
    request: Request,
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:delete:global")),
    service: ResourceSampleService = Depends(get_admin_sample_service),
):
    """Delete an admin sample.

    Args:
        sample_id: Sample identifier to delete.
        user: Authenticated user performing the mutation.
        service: Admin sample workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    result = service.delete(sample_id=sample_id)
    request.state.audit_resource = {
        "type": "sample",
        "id": result.get("meta", {}).get("sample_oid") or sample_id,
        "name": result.get("meta", {}).get("sample_name"),
        "message": f"Deleted sample {result.get('meta', {}).get('sample_name') or sample_id}",
        "metadata": {
            "sample_oid": result.get("meta", {}).get("sample_oid") or sample_id,
            "deletion_results": result.get("meta", {}).get("results", []),
        },
    }
    return util.common.convert_to_serializable(result)
