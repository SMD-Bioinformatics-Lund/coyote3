"""Configurable assay config router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from api.app.container import util
from api.app.deps.application import get_assay_configurations, get_reference_data
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.interfaces.http.v1.admin.resources.audit import set_managed_resource_audit_context
from api.security.access import ApiUser, require_access
from coyote3.application.operations.administration import AssayConfigurations, ReferenceData
from coyote3.contracts.admin import (
    AdminAspcContextPayload,
    AdminAspcCreateContextPayload,
    AdminAspcListPayload,
    AdminChangePayload,
    AdminExistsPayload,
)
from coyote3.contracts.resource_fields import ConfigurationField, FieldValue
from coyote3.contracts.resource_metadata import ConfigurationMetadata

router = APIRouter(tags=[TAG_ADMIN_ASSAYS])


@router.get("/api/v1/resources/aspc", response_model=AdminAspcListPayload)
def list_aspc_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="assay.config:list")),
    service: AssayConfigurations = Depends(get_assay_configurations),
):
    """Return the assay-config admin list.

    \u000c

    Args:
        q: Case-insensitive text search across configuration identifiers and
            metadata; blank text omits the search filter.
        page: One-based result page; defaults to 1.
        per_page: Page size from 1 to 200; defaults to 30.
        user: Authenticated user requesting the list.
        service: Assay-config workflow service.

    Returns:
        dict: Admin list payload for assay configs.
    """
    _ = user
    return util.common.convert_to_serializable(service.list_aspc(q=q, page=page, per_page=per_page))


@router.get("/api/v1/resources/aspc/create_context", response_model=AdminAspcCreateContextPayload)
def create_aspc_context_read(
    category: str = Query(default="DNA"),
    user: ApiUser = Depends(require_access(permission="assay.config:create")),
    service: AssayConfigurations = Depends(get_assay_configurations),
):
    """Return create-form context for an assay config.

    \u000c

    Args:
        category: Requested assay category.
        user: Authenticated user requesting create context.
        service: Assay-config workflow service.

    Returns:
        dict: Create-context payload for assay configs.
    """
    return util.common.convert_to_serializable(service.create_aspc_context(category=category))


@router.get("/api/v1/resources/aspc/{assay_id}/context", response_model=AdminAspcContextPayload)
def aspc_context_read(
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="assay.config:view")),
    service: AssayConfigurations = Depends(get_assay_configurations),
):
    """Return edit-form context for an assay config.

    \u000c

    Args:
        assay_id: Assay-config identifier to load.
        user: Authenticated user requesting edit context.
        service: Assay-config workflow service.

    Returns:
        dict: Edit-context payload for the assay config.
    """
    _ = user
    return util.common.convert_to_serializable(service.aspc_context(assay_id=assay_id))


@router.get("/api/v1/resources/aspc/{aspc_id}/metadata", response_model=ConfigurationMetadata)
def aspc_metadata_read(
    aspc_id: str,
    user: ApiUser = Depends(require_access(permission="assay.config:view")),
    service: ReferenceData = Depends(get_reference_data),
):
    """Return permitted active configuration metadata; requires assay.config:view."""
    return service.configuration_metadata(aspc_id)


@router.get(
    "/api/v1/resources/aspc/{aspc_id}/fields/{field}",
    response_model=FieldValue,
)
def aspc_field_read(
    aspc_id: str,
    field: ConfigurationField,
    user: ApiUser = Depends(require_access(permission="assay.config:view")),
    service: ReferenceData = Depends(get_reference_data),
):
    """Return one configuration value; requires assay.config:view."""
    _ = user
    return util.common.convert_to_serializable(service.configuration_field(aspc_id, field))


@router.post(
    "/api/v1/resources/aspc",
    response_model=AdminChangePayload,
    status_code=201,
    summary="Create assay config",
)
def create_aspc_change(
    request: Request,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="assay.config:create")),
    service: AssayConfigurations = Depends(get_assay_configurations),
):
    """Create an assay config.

    \u000c

    Args:
        request: Request receiving audit metadata for the created configuration.
        payload: Submitted assay-config payload.
        user: Authenticated user performing the mutation.
        service: Assay-config workflow service.

    Returns:
        dict: Mutation response payload.
    """
    result = service.create_aspc(payload=payload)
    set_managed_resource_audit_context(
        request, resource_type="aspc", action="created", result=result
    )
    return util.common.convert_to_serializable(result)


@router.put(
    "/api/v1/resources/aspc/{assay_id}",
    response_model=AdminChangePayload,
    summary="Update assay config",
)
def update_aspc_change(
    request: Request,
    assay_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="assay.config:edit")),
    service: AssayConfigurations = Depends(get_assay_configurations),
):
    """Update an assay config.

    \u000c

    Args:
        request: Request receiving audit metadata for the updated configuration.
        assay_id: Assay-config identifier to update.
        payload: Submitted assay-config payload.
        user: Authenticated user performing the mutation.
        service: Assay-config workflow service.

    Returns:
        dict: Mutation response payload.
    """
    result = service.update_aspc(assay_id=assay_id, payload=payload)
    set_managed_resource_audit_context(
        request, resource_type="aspc", action="updated", result=result
    )
    return util.common.convert_to_serializable(result)


@router.patch(
    "/api/v1/resources/aspc/{assay_id}/status",
    response_model=AdminChangePayload,
    summary="Toggle assay config status",
)
def toggle_aspc_change(
    request: Request,
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="assay.config:edit")),
    service: AssayConfigurations = Depends(get_assay_configurations),
):
    """Toggle assay-config active status.

    \u000c

    Args:
        request: Request receiving audit metadata for the configuration status change.
        assay_id: Assay-config identifier to toggle.
        user: Authenticated user performing the mutation.
        service: Assay-config workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    result = service.toggle_aspc(assay_id=assay_id)
    set_managed_resource_audit_context(
        request, resource_type="aspc", action="updated", result=result
    )
    return util.common.convert_to_serializable(result)


@router.delete(
    "/api/v1/resources/aspc/{assay_id}",
    response_model=AdminChangePayload,
    summary="Delete assay config",
)
def delete_aspc_change(
    request: Request,
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="assay.config:delete")),
    service: AssayConfigurations = Depends(get_assay_configurations),
):
    """Delete an assay config.

    \u000c

    Args:
        request: Request receiving audit metadata for the deleted configuration.
        assay_id: Assay-config identifier to delete.
        user: Authenticated user performing the mutation.
        service: Assay-config workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    result = service.delete_aspc(assay_id=assay_id)
    set_managed_resource_audit_context(
        request, resource_type="aspc", action="deleted", result=result
    )
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/resources/aspc/validate_aspc_id", response_model=AdminExistsPayload)
def validate_aspc_id_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="assay.config:create")),
    service: AssayConfigurations = Depends(get_assay_configurations),
):
    """Validate whether an aspc_id already exists."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.validate_aspc_id(payload=payload)}
    )
