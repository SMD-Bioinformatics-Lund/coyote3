"""Configurable sample resource router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminChangePayload,
    AdminSampleContextPayload,
    AdminSamplesListPayload,
)
from api.deps.services import get_admin_sample_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.resources.sample import ResourceSampleService

router = APIRouter(tags=["resource-samples"])


@router.get("/api/v1/resources/samples", response_model=AdminSamplesListPayload)
def list_admin_samples_read(
    search: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(
        require_access(permission="view_sample_global", min_role="developer", min_level=9999)
    ),
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
        service.list_payload(assays=user.assays, search=search, page=page, per_page=per_page)
    )


@router.get(
    "/api/v1/resources/samples/{sample_id}/context", response_model=AdminSampleContextPayload
)
def admin_sample_context_read(
    sample_id: str,
    user: ApiUser = Depends(
        require_access(permission="edit_sample", min_role="developer", min_level=9999)
    ),
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
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(
        require_access(permission="edit_sample", min_role="developer", min_level=9999)
    ),
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
    return util.common.convert_to_serializable(
        service.update(sample_id=sample_id, payload=payload, actor_username=user.username)
    )


@router.delete(
    "/api/v1/resources/samples/{sample_id}",
    response_model=AdminChangePayload,
    summary="Delete admin sample",
)
def delete_sample_change(
    sample_id: str,
    user: ApiUser = Depends(
        require_access(permission="delete_sample_global", min_role="developer", min_level=9999)
    ),
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
    return util.common.convert_to_serializable(service.delete(sample_id=sample_id))
