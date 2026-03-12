"""Configurable sample resource router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import AdminMutationPayload, AdminSampleContextPayload, AdminSamplesListPayload
from api.deps.services import get_admin_sample_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.admin_resource_service import AdminSampleService

router = APIRouter(tags=["resource-samples"])


@router.get("/api/v1/resources/samples", response_model=AdminSamplesListPayload)
def list_admin_samples_read(
    search: str = Query(default=""),
    user: ApiUser = Depends(require_access(permission="view_sample_global", min_role="developer", min_level=9999)),
    service: AdminSampleService = Depends(get_admin_sample_service),
):
    """List admin samples read.

    Args:
        search (str): Value for ``search``.
        user (ApiUser): Value for ``user``.
        service (AdminSampleService): Value for ``service``.

    Returns:
        The function result.
    """
    return util.common.convert_to_serializable(service.list_payload(assays=user.assays, search=search))


@router.get("/api/v1/resources/samples/{sample_id}/context", response_model=AdminSampleContextPayload)
def admin_sample_context_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="developer", min_level=9999)),
    service: AdminSampleService = Depends(get_admin_sample_service),
):
    """Handle admin sample context read.

    Args:
        sample_id (str): Value for ``sample_id``.
        user (ApiUser): Value for ``user``.
        service (AdminSampleService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.context_payload(sample_id=sample_id))


@router.put("/api/v1/resources/samples/{sample_id}", response_model=AdminMutationPayload, summary="Update admin sample")
def update_sample_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="developer", min_level=9999)),
    service: AdminSampleService = Depends(get_admin_sample_service),
):
    """Update sample mutation.

    Args:
        sample_id (str): Value for ``sample_id``.
        payload (dict): Value for ``payload``.
        user (ApiUser): Value for ``user``.
        service (AdminSampleService): Value for ``service``.

    Returns:
        The function result.
    """
    return util.common.convert_to_serializable(
        service.update(sample_id=sample_id, payload=payload, actor_username=user.username)
    )


@router.delete("/api/v1/resources/samples/{sample_id}", response_model=AdminMutationPayload, summary="Delete admin sample")
def delete_sample_mutation(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="delete_sample_global", min_role="developer", min_level=9999)),
    service: AdminSampleService = Depends(get_admin_sample_service),
):
    """Delete sample mutation.

    Args:
        sample_id (str): Value for ``sample_id``.
        user (ApiUser): Value for ``user``.
        service (AdminSampleService): Value for ``service``.

    Returns:
        The function result.
    """
    _ = user
    return util.common.convert_to_serializable(service.delete(sample_id=sample_id))
