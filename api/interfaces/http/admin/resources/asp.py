"""Configurable assay panel router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from api.app.container import util
from api.app.deps.services import (
    get_admin_assay_group_service,
    get_admin_panel_service,
    get_admin_subpanel_service,
)
from api.application.resources.asp import AspService
from api.application.resources.assay_groups import AssayGroupService
from api.application.resources.subpanels import SubpanelService
from api.contracts.admin import (
    AdminChangePayload,
    AdminExistsPayload,
    AdminPanelContextPayload,
    AdminPanelCreateContextPayload,
    AdminPanelsListPayload,
)
from api.contracts.schemas.assay_groups import (
    AssayGroupCreate,
    AssayGroupImpact,
    AssayGroupsPayload,
    AssayGroupStatus,
)
from api.contracts.schemas.subpanels import (
    SharedSubpanelCreate,
    SharedSubpanelUpdate,
    SubpanelAssociationUpdate,
    SubpanelCreate,
    SubpanelDefinitionsPayload,
    SubpanelsPayload,
    SubpanelUpdate,
)
from api.interfaces.http.admin.resources.audit import set_managed_resource_audit_context
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_ADMIN_ASSAYS])


@router.get("/api/v1/resources/assay-groups/{group_id}/impact", response_model=AssayGroupImpact)
def assay_group_impact(
    group_id: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: AssayGroupService = Depends(get_admin_assay_group_service),
):
    """Inspect status and affected assays; requires assay.panel:view."""
    return util.common.convert_to_serializable(service.impact(group_id))


@router.patch("/api/v1/resources/assay-groups/{group_id}/status", response_model=AdminChangePayload)
def change_assay_group_status(
    request: Request,
    group_id: str,
    payload: AssayGroupStatus,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssayGroupService = Depends(get_admin_assay_group_service),
):
    """Confirm availability with a reason and current revision; requires assay.panel:edit."""
    result = service.change_status(group_id, payload, actor=user.username)
    set_managed_resource_audit_context(
        request, resource_type="assay_group", action="updated", result=result
    )
    return result


@router.get("/api/v1/resources/assay-groups", response_model=AssayGroupsPayload)
def list_assay_groups(
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: AssayGroupService = Depends(get_admin_assay_group_service),
):
    """List registered system and custom groups; requires assay.panel:view."""
    return util.common.convert_to_serializable(service.list_payload())


@router.post("/api/v1/resources/assay-groups", response_model=AdminChangePayload, status_code=201)
def create_assay_group(
    request: Request,
    payload: AssayGroupCreate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssayGroupService = Depends(get_admin_assay_group_service),
):
    """Register a custom assay group; requires assay.panel:edit and records an audit event."""
    result = service.create(payload, actor=user.username)
    set_managed_resource_audit_context(
        request, resource_type="assay_group", action="created", result=result
    )
    return result


@router.post("/api/v1/resources/subpanels", response_model=AdminChangePayload, status_code=201)
def create_shared_subpanel(
    request: Request,
    payload: SharedSubpanelCreate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: SubpanelService = Depends(get_admin_subpanel_service),
):
    """Create one shared definition and selected assay links; requires assay.panel:edit."""
    result = service.create_definition(payload, actor=user.username)
    set_managed_resource_audit_context(
        request, resource_type="subpanel", action="created", result=result
    )
    return result


@router.patch(
    "/api/v1/resources/asp/{assay_panel_id}/subpanels/{subpanel_id}/status",
    response_model=AdminChangePayload,
)
def change_subpanel_association_status(
    request: Request,
    assay_panel_id: str,
    subpanel_id: str,
    payload: SubpanelAssociationUpdate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: SubpanelService = Depends(get_admin_subpanel_service),
):
    """Enable or disable only this assay link; requires assay.panel:edit."""
    result = service.set_association_status(
        assay_panel_id, subpanel_id, payload, actor=user.username
    )
    set_managed_resource_audit_context(
        request, resource_type="assay_subpanel", action="updated", result=result
    )
    return result


@router.get("/api/v1/resources/subpanels", response_model=SubpanelDefinitionsPayload)
def list_shared_subpanels(
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: SubpanelService = Depends(get_admin_subpanel_service),
):
    """List shared definitions; requires assay.panel:view."""
    return util.common.convert_to_serializable(service.definitions_payload())


@router.put("/api/v1/resources/subpanels/{subpanel_id}", response_model=AdminChangePayload)
def revise_shared_subpanel(
    request: Request,
    subpanel_id: str,
    payload: SharedSubpanelUpdate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: SubpanelService = Depends(get_admin_subpanel_service),
):
    """Revise shared metadata for all associated assays; requires assay.panel:edit."""
    result = service.revise_definition(subpanel_id, payload, actor=user.username)
    set_managed_resource_audit_context(
        request, resource_type="subpanel", action="updated", result=result
    )
    return result


@router.get("/api/v1/resources/asp/{assay_panel_id}/subpanels", response_model=SubpanelsPayload)
def list_subpanels(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: SubpanelService = Depends(get_admin_subpanel_service),
):
    """List current and retired subpanels; requires assay.panel:view."""
    return util.common.convert_to_serializable(service.list_payload(assay_panel_id))


@router.post(
    "/api/v1/resources/asp/{assay_panel_id}/subpanels",
    response_model=AdminChangePayload,
    status_code=201,
)
def create_subpanel(
    request: Request,
    assay_panel_id: str,
    payload: SubpanelCreate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: SubpanelService = Depends(get_admin_subpanel_service),
):
    """Register a subpanel under an existing assay; requires assay.panel:edit."""
    result = service.save(assay_panel_id, payload, actor=user.username)
    set_managed_resource_audit_context(
        request,
        resource_type="assay_subpanel",
        action="created",
        result=result,
    )
    return result


@router.put(
    "/api/v1/resources/asp/{assay_panel_id}/subpanels/{subpanel_id}",
    response_model=AdminChangePayload,
)
def update_subpanel(
    request: Request,
    assay_panel_id: str,
    subpanel_id: str,
    payload: SubpanelUpdate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: SubpanelService = Depends(get_admin_subpanel_service),
):
    """Revise or retire a subpanel; requires assay.panel:edit and its current version."""
    result = service.save(assay_panel_id, payload, actor=user.username, subpanel_id=subpanel_id)
    set_managed_resource_audit_context(
        request,
        resource_type="assay_subpanel",
        action="updated",
        result=result,
    )
    return result


@router.post(
    "/api/v1/resources/asp",
    response_model=AdminChangePayload,
    status_code=201,
    summary="Create assay panel",
)
def create_asp_change(
    request: Request,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="assay.panel:create")),
    service: AspService = Depends(get_admin_panel_service),
):
    """Create an assay panel.

    \u000c

    Args:
        request: Request receiving audit metadata for the created panel.
        payload: Submitted assay-panel payload.
        user: Authenticated user performing the mutation.
        service: Assay-panel workflow service.

    Returns:
        dict: Mutation response payload.
    """
    result = service.create(payload=payload, actor_username=user.username)
    set_managed_resource_audit_context(
        request, resource_type="asp", action="created", result=result
    )
    return util.common.convert_to_serializable(result)


@router.get("/api/v1/resources/asp", response_model=AdminPanelsListPayload)
def list_asp_read(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="assay.panel:list")),
    service: AspService = Depends(get_admin_panel_service),
):
    """Return the assay-panel admin list.

    \u000c

    Args:
        q: Case-insensitive text search across panel identifiers and metadata;
            blank text omits the search filter.
        page: One-based result page; defaults to 1.
        per_page: Page size from 1 to 200; defaults to 30.
        user: Authenticated user requesting the list.
        service: Assay-panel workflow service.

    Returns:
        dict: Admin list payload for assay panels.
    """
    _ = user
    return util.common.convert_to_serializable(
        service.list_payload(q=q, page=page, per_page=per_page)
    )


@router.get("/api/v1/resources/asp/create_context", response_model=AdminPanelCreateContextPayload)
def create_asp_context_read(
    user: ApiUser = Depends(require_access(permission="assay.panel:create")),
    service: AspService = Depends(get_admin_panel_service),
):
    """Return create-form context for an assay panel.

    \u000c

    Args:
        user: Authenticated user requesting create context.
        service: Assay-panel workflow service.

    Returns:
        dict: Create-context payload for assay panels.
    """
    return util.common.convert_to_serializable(
        service.create_context_payload(actor_username=user.username)
    )


@router.get(
    "/api/v1/resources/asp/{assay_panel_id}/context", response_model=AdminPanelContextPayload
)
def asp_context_read(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: AspService = Depends(get_admin_panel_service),
):
    """Return edit-form context for an assay panel.

    \u000c

    Args:
        assay_panel_id: Assay-panel identifier to load.
        user: Authenticated user requesting edit context.
        service: Assay-panel workflow service.

    Returns:
        dict: Edit-context payload for the assay panel.
    """
    _ = user
    return util.common.convert_to_serializable(service.context_payload(panel_id=assay_panel_id))


@router.put(
    "/api/v1/resources/asp/{assay_panel_id}",
    response_model=AdminChangePayload,
    summary="Update assay panel",
)
def update_asp_change(
    request: Request,
    assay_panel_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AspService = Depends(get_admin_panel_service),
):
    """Update an assay panel.

    \u000c

    Args:
        request: Request receiving audit metadata for the updated panel.
        assay_panel_id: Assay-panel identifier to update.
        payload: Submitted assay-panel payload.
        user: Authenticated user performing the mutation.
        service: Assay-panel workflow service.

    Returns:
        dict: Mutation response payload.
    """
    result = service.update(panel_id=assay_panel_id, payload=payload, actor_username=user.username)
    set_managed_resource_audit_context(
        request, resource_type="asp", action="updated", result=result
    )
    return util.common.convert_to_serializable(result)


@router.patch(
    "/api/v1/resources/asp/{assay_panel_id}/status",
    response_model=AdminChangePayload,
    summary="Toggle assay panel status",
)
def toggle_asp_change(
    request: Request,
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AspService = Depends(get_admin_panel_service),
):
    """Toggle assay-panel active status.

    \u000c

    Args:
        request: Request receiving audit metadata for the panel status change.
        assay_panel_id: Assay-panel identifier to toggle.
        user: Authenticated user performing the mutation.
        service: Assay-panel workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    result = service.toggle(panel_id=assay_panel_id)
    set_managed_resource_audit_context(
        request, resource_type="asp", action="updated", result=result
    )
    return util.common.convert_to_serializable(result)


@router.delete(
    "/api/v1/resources/asp/{assay_panel_id}",
    response_model=AdminChangePayload,
    summary="Delete assay panel",
)
def delete_asp_change(
    request: Request,
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:delete")),
    service: AspService = Depends(get_admin_panel_service),
):
    """Delete an assay panel.

    \u000c

    Args:
        request: Request receiving audit metadata for the deleted panel.
        assay_panel_id: Assay-panel identifier to delete.
        user: Authenticated user performing the mutation.
        service: Assay-panel workflow service.

    Returns:
        dict: Mutation response payload.
    """
    _ = user
    result = service.delete(panel_id=assay_panel_id)
    set_managed_resource_audit_context(
        request, resource_type="asp", action="deleted", result=result
    )
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/resources/asp/validate_asp_id", response_model=AdminExistsPayload)
def validate_asp_id_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="assay.panel:create")),
    service: AspService = Depends(get_admin_panel_service),
):
    """Validate whether an asp_id already exists."""
    _ = user
    return util.common.convert_to_serializable(
        {"exists": service.panel_exists(asp_id=str(payload.get("asp_id", "")))}
    )
