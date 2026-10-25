"""Configurable assay panel router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request

from api.app.container import util
from api.app.deps.application import get_assay_groups, get_assays, get_diagnoses, get_reference_data
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.interfaces.http.v1.admin.resources.audit import set_managed_resource_audit_context
from api.security.access import ApiUser, require_access
from coyote3.application.operations.administration import (
    AssayGroups,
    Assays,
    Diagnoses,
    ReferenceData,
)
from coyote3.contracts.admin import (
    AdminChangePayload,
    AdminExistsPayload,
    AdminPanelContextPayload,
    AdminPanelCreateContextPayload,
    AdminPanelsListPayload,
)
from coyote3.contracts.resource_fields import (
    AssayField,
    DiagnosisField,
    FieldValue,
    GroupField,
)
from coyote3.contracts.resource_metadata import AssayMetadata, DiagnosisMetadata, GroupMetadata
from coyote3.contracts.schemas.assay_groups import (
    AssayGroupCreate,
    AssayGroupImpact,
    AssayGroupsPayload,
    AssayGroupStatus,
)
from coyote3.contracts.schemas.diagnoses import (
    DiagnosesPayload,
    DiagnosisAssociationUpdate,
    DiagnosisCreate,
    DiagnosisDefinitionsPayload,
    DiagnosisUpdate,
    SharedDiagnosisCreate,
    SharedDiagnosisUpdate,
)

router = APIRouter(tags=[TAG_ADMIN_ASSAYS])


@router.get("/api/v1/resources/assay-groups/{group_id}/metadata", response_model=GroupMetadata)
def assay_group_metadata_read(
    group_id: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: ReferenceData = Depends(get_reference_data),
):
    """Return permitted group metadata; requires assay.panel:view."""
    return service.group_metadata(group_id)


@router.get("/api/v1/resources/diagnoses/{diagnosis_id}/metadata", response_model=DiagnosisMetadata)
def diagnosis_metadata_read(
    diagnosis_id: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: ReferenceData = Depends(get_reference_data),
):
    """Return permitted diagnosis metadata; requires assay.panel:view."""
    return service.diagnosis_metadata(diagnosis_id)


@router.get(
    "/api/v1/resources/assay-groups/{group_id}/fields/{field}",
    response_model=FieldValue,
)
def assay_group_field_read(
    group_id: str,
    field: GroupField,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: ReferenceData = Depends(get_reference_data),
):
    """Return one biological group value; requires assay.panel:view."""
    _ = user
    return util.common.convert_to_serializable(service.group_field(group_id, field))


@router.get(
    "/api/v1/resources/diagnoses/{diagnosis_id}/fields/{field}",
    response_model=FieldValue,
)
def diagnosis_field_read(
    diagnosis_id: str,
    field: DiagnosisField,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: ReferenceData = Depends(get_reference_data),
):
    """Return one shared diagnosis value; requires assay.panel:view."""
    _ = user
    return util.common.convert_to_serializable(service.diagnosis_field(diagnosis_id, field))


@router.get("/api/v1/resources/assay-groups/{group_id}/impact", response_model=AssayGroupImpact)
def assay_group_impact(
    group_id: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: AssayGroups = Depends(get_assay_groups),
):
    """Inspect status and affected assays; requires assay.panel:view."""
    return util.common.convert_to_serializable(service.assay_group_impact(group_id=group_id))


@router.patch("/api/v1/resources/assay-groups/{group_id}/status", response_model=AdminChangePayload)
def change_assay_group_status(
    request: Request,
    group_id: str,
    payload: AssayGroupStatus,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssayGroups = Depends(get_assay_groups),
):
    """Confirm availability with a reason and current revision; requires assay.panel:edit."""
    result = service.change_assay_group_status(group_id=group_id, payload=payload)
    set_managed_resource_audit_context(
        request, resource_type="assay_group", action="updated", result=result
    )
    return result


@router.get("/api/v1/resources/assay-groups", response_model=AssayGroupsPayload)
def list_assay_groups(
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: AssayGroups = Depends(get_assay_groups),
):
    """List registered system and custom groups; requires assay.panel:view."""
    return util.common.convert_to_serializable(service.list_assay_groups())


@router.post("/api/v1/resources/assay-groups", response_model=AdminChangePayload, status_code=201)
def create_assay_group(
    request: Request,
    payload: AssayGroupCreate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: AssayGroups = Depends(get_assay_groups),
):
    """Register a custom assay group; requires assay.panel:edit and records an audit event."""
    result = service.create_assay_group(payload=payload)
    set_managed_resource_audit_context(
        request, resource_type="assay_group", action="created", result=result
    )
    return result


@router.post("/api/v1/resources/diagnoses", response_model=AdminChangePayload, status_code=201)
def create_shared_diagnosis(
    request: Request,
    payload: SharedDiagnosisCreate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: Diagnoses = Depends(get_diagnoses),
):
    """Create one shared definition and selected assay links; requires assay.panel:edit."""
    result = service.create_shared_diagnosis(payload=payload)
    set_managed_resource_audit_context(
        request, resource_type="diagnosis", action="created", result=result
    )
    return result


@router.patch(
    "/api/v1/resources/asp/{assay_panel_id}/diagnoses/{diagnosis_id}/status",
    response_model=AdminChangePayload,
)
def change_diagnosis_association_status(
    request: Request,
    assay_panel_id: str,
    diagnosis_id: str,
    payload: DiagnosisAssociationUpdate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: Diagnoses = Depends(get_diagnoses),
):
    """Enable or disable only this assay link; requires assay.panel:edit."""
    result = service.change_diagnosis_association_status(
        assay_panel_id=assay_panel_id, diagnosis_id=diagnosis_id, payload=payload
    )
    set_managed_resource_audit_context(
        request, resource_type="assay_diagnosis", action="updated", result=result
    )
    return result


@router.get("/api/v1/resources/diagnoses", response_model=DiagnosisDefinitionsPayload)
def list_shared_diagnoses(
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: Diagnoses = Depends(get_diagnoses),
):
    """List shared definitions; requires assay.panel:view."""
    return util.common.convert_to_serializable(service.list_shared_diagnoses())


@router.put("/api/v1/resources/diagnoses/{diagnosis_id}", response_model=AdminChangePayload)
def revise_shared_diagnosis(
    request: Request,
    diagnosis_id: str,
    payload: SharedDiagnosisUpdate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: Diagnoses = Depends(get_diagnoses),
):
    """Revise shared metadata for all associated assays; requires assay.panel:edit."""
    result = service.revise_shared_diagnosis(diagnosis_id=diagnosis_id, payload=payload)
    set_managed_resource_audit_context(
        request, resource_type="diagnosis", action="updated", result=result
    )
    return result


@router.get("/api/v1/resources/asp/{assay_panel_id}/diagnoses", response_model=DiagnosesPayload)
def list_diagnoses(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: Diagnoses = Depends(get_diagnoses),
):
    """List current and retired diagnoses; requires assay.panel:view."""
    return util.common.convert_to_serializable(
        service.list_diagnoses(assay_panel_id=assay_panel_id)
    )


@router.post(
    "/api/v1/resources/asp/{assay_panel_id}/diagnoses",
    response_model=AdminChangePayload,
    status_code=201,
)
def create_diagnosis(
    request: Request,
    assay_panel_id: str,
    payload: DiagnosisCreate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: Diagnoses = Depends(get_diagnoses),
):
    """Register a diagnosis under an existing assay; requires assay.panel:edit."""
    result = service.create_diagnosis(assay_panel_id=assay_panel_id, payload=payload)
    set_managed_resource_audit_context(
        request,
        resource_type="assay_diagnosis",
        action="created",
        result=result,
    )
    return result


@router.put(
    "/api/v1/resources/asp/{assay_panel_id}/diagnoses/{diagnosis_id}",
    response_model=AdminChangePayload,
)
def update_diagnosis(
    request: Request,
    assay_panel_id: str,
    diagnosis_id: str,
    payload: DiagnosisUpdate,
    user: ApiUser = Depends(require_access(permission="assay.panel:edit")),
    service: Diagnoses = Depends(get_diagnoses),
):
    """Revise or retire a diagnosis; requires assay.panel:edit and its current version."""
    result = service.update_diagnosis(
        assay_panel_id=assay_panel_id, diagnosis_id=diagnosis_id, payload=payload
    )
    set_managed_resource_audit_context(
        request,
        resource_type="assay_diagnosis",
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
    service: Assays = Depends(get_assays),
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
    result = service.create_asp(payload=payload)
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
    service: Assays = Depends(get_assays),
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
    return util.common.convert_to_serializable(service.list_asp(q=q, page=page, per_page=per_page))


@router.get("/api/v1/resources/asp/create_context", response_model=AdminPanelCreateContextPayload)
def create_asp_context_read(
    user: ApiUser = Depends(require_access(permission="assay.panel:create")),
    service: Assays = Depends(get_assays),
):
    """Return create-form context for an assay panel.

    \u000c

    Args:
        user: Authenticated user requesting create context.
        service: Assay-panel workflow service.

    Returns:
        dict: Create-context payload for assay panels.
    """
    return util.common.convert_to_serializable(service.create_asp_context())


@router.get("/api/v1/resources/asp/{assay_panel_id}/metadata", response_model=AssayMetadata)
def assay_metadata_read(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: ReferenceData = Depends(get_reference_data),
):
    """Return permitted active assay metadata; requires assay.panel:view."""
    return service.assay_metadata(assay_panel_id)


@router.get("/api/v1/resources/asp/{assay_panel_id}/fields/{field}", response_model=FieldValue)
def assay_field_read(
    assay_panel_id: str,
    field: AssayField,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: ReferenceData = Depends(get_reference_data),
):
    """Return one assay value; requires assay.panel:view."""
    _ = user
    return util.common.convert_to_serializable(service.assay_field(assay_panel_id, field))


@router.get(
    "/api/v1/resources/asp/{assay_panel_id}/context", response_model=AdminPanelContextPayload
)
def asp_context_read(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="assay.panel:view")),
    service: Assays = Depends(get_assays),
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
    return util.common.convert_to_serializable(service.asp_context(assay_panel_id=assay_panel_id))


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
    service: Assays = Depends(get_assays),
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
    result = service.update_asp(assay_panel_id=assay_panel_id, payload=payload)
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
    service: Assays = Depends(get_assays),
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
    result = service.toggle_asp(assay_panel_id=assay_panel_id)
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
    service: Assays = Depends(get_assays),
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
    result = service.delete_asp(assay_panel_id=assay_panel_id)
    set_managed_resource_audit_context(
        request, resource_type="asp", action="deleted", result=result
    )
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/resources/asp/validate_asp_id", response_model=AdminExistsPayload)
def validate_asp_id_change(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="assay.panel:create")),
    service: Assays = Depends(get_assays),
):
    """Validate whether an asp_id already exists."""
    _ = user
    return util.common.convert_to_serializable({"exists": service.validate_asp_id(payload=payload)})
