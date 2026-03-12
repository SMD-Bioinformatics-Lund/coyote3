"""Canonical router for admin resource endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.admin import (
    AdminAspcContextPayload,
    AdminAspcCreateContextPayload,
    AdminAspcListPayload,
    AdminGenelistContextPayload,
    AdminGenelistCreateContextPayload,
    AdminGenelistsListPayload,
    AdminGenelistViewContextPayload,
    AdminMutationPayload,
    AdminPanelContextPayload,
    AdminPanelCreateContextPayload,
    AdminPanelsListPayload,
    AdminSampleContextPayload,
    AdminSamplesListPayload,
    AdminSchemaContextPayload,
    AdminSchemasListPayload,
)
from api.deps.services import (
    get_admin_aspc_service,
    get_admin_genelist_service,
    get_admin_panel_service,
    get_admin_sample_service,
    get_admin_schema_service,
)
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.admin_resource_service import (
    AdminAspcService,
    AdminGenelistService,
    AdminPanelService,
    AdminSampleService,
    AdminSchemaService,
)

router = APIRouter(tags=["admin-resources"])


@router.post("/api/v1/admin/asp", response_model=AdminMutationPayload, status_code=201, summary="Create assay panel")
def create_asp_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_asp", min_role="manager", min_level=99)),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    _ = user
    return util.common.convert_to_serializable(service.create(payload=payload))


@router.get("/api/v1/admin/asp", response_model=AdminPanelsListPayload)
def list_asp_read(
    user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9)),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    _ = user
    return util.common.convert_to_serializable(service.list_payload())


@router.get("/api/v1/admin/asp/create_context", response_model=AdminPanelCreateContextPayload)
def create_asp_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_asp", min_role="manager", min_level=99)),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    return util.common.convert_to_serializable(
        service.create_context_payload(schema_id=schema_id, actor_username=user.username)
    )


@router.get("/api/v1/admin/asp/{assay_panel_id}/context", response_model=AdminPanelContextPayload)
def asp_context_read(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9)),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    _ = user
    return util.common.convert_to_serializable(service.context_payload(panel_id=assay_panel_id))


@router.put("/api/v1/admin/asp/{assay_panel_id}", response_model=AdminMutationPayload, summary="Update assay panel")
def update_asp_mutation(
    assay_panel_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_asp", min_role="manager", min_level=99)),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    _ = user
    return util.common.convert_to_serializable(service.update(panel_id=assay_panel_id, payload=payload))


@router.patch("/api/v1/admin/asp/{assay_panel_id}/status", response_model=AdminMutationPayload, summary="Toggle assay panel status")
def toggle_asp_mutation(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="edit_asp", min_role="manager", min_level=99)),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    _ = user
    return util.common.convert_to_serializable(service.toggle(panel_id=assay_panel_id))


@router.delete("/api/v1/admin/asp/{assay_panel_id}", response_model=AdminMutationPayload, summary="Delete assay panel")
def delete_asp_mutation(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="delete_asp", min_role="admin", min_level=99999)),
    service: AdminPanelService = Depends(get_admin_panel_service),
):
    _ = user
    return util.common.convert_to_serializable(service.delete(panel_id=assay_panel_id))


@router.post("/api/v1/admin/genelists", response_model=AdminMutationPayload, status_code=201, summary="Create genelist")
def create_genelist_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_isgl", min_role="manager", min_level=99)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.create(payload=payload))


@router.get("/api/v1/admin/genelists", response_model=AdminGenelistsListPayload)
def list_genelists_read(
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.list_payload())


@router.get("/api/v1/admin/genelists/create_context", response_model=AdminGenelistCreateContextPayload)
def create_genelist_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_isgl", min_role="manager", min_level=99)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    return util.common.convert_to_serializable(
        service.create_context_payload(schema_id=schema_id, actor_username=user.username)
    )


@router.get("/api/v1/admin/genelists/{genelist_id}/context", response_model=AdminGenelistContextPayload)
def genelist_context_read(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.context_payload(genelist_id=genelist_id))


@router.get("/api/v1/admin/genelists/{genelist_id}/view_context", response_model=AdminGenelistViewContextPayload)
def genelist_view_context_read(
    genelist_id: str,
    assay: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.view_context_payload(genelist_id=genelist_id, assay=assay))


@router.put("/api/v1/admin/genelists/{genelist_id}", response_model=AdminMutationPayload, summary="Update genelist")
def update_genelist_mutation(
    genelist_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_isgl", min_role="manager", min_level=99)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.update(genelist_id=genelist_id, payload=payload))


@router.patch("/api/v1/admin/genelists/{genelist_id}/status", response_model=AdminMutationPayload, summary="Toggle genelist status")
def toggle_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="edit_isgl", min_role="manager", min_level=99)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.toggle(genelist_id=genelist_id))


@router.delete("/api/v1/admin/genelists/{genelist_id}", response_model=AdminMutationPayload, summary="Delete genelist")
def delete_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="delete_isgl", min_role="admin", min_level=99999)),
    service: AdminGenelistService = Depends(get_admin_genelist_service),
):
    _ = user
    return util.common.convert_to_serializable(service.delete(genelist_id=genelist_id))


@router.get("/api/v1/admin/aspc", response_model=AdminAspcListPayload)
def list_aspc_read(
    user: ApiUser = Depends(require_access(permission="view_aspc", min_role="user", min_level=9)),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    _ = user
    return util.common.convert_to_serializable(service.list_payload())


@router.get("/api/v1/admin/aspc/create_context", response_model=AdminAspcCreateContextPayload)
def create_aspc_context_read(
    category: str = Query(default="DNA"),
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_aspc", min_role="manager", min_level=99)),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    return util.common.convert_to_serializable(
        service.create_context_payload(category=category, schema_id=schema_id, actor_username=user.username)
    )


@router.get("/api/v1/admin/aspc/{assay_id}/context", response_model=AdminAspcContextPayload)
def aspc_context_read(
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="view_aspc", min_role="user", min_level=9)),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    _ = user
    return util.common.convert_to_serializable(service.context_payload(assay_id=assay_id))


@router.post("/api/v1/admin/aspc", response_model=AdminMutationPayload, status_code=201, summary="Create assay config")
def create_aspc_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_aspc", min_role="manager", min_level=99)),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    _ = user
    return util.common.convert_to_serializable(service.create(payload=payload))


@router.put("/api/v1/admin/aspc/{assay_id}", response_model=AdminMutationPayload, summary="Update assay config")
def update_aspc_mutation(
    assay_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_aspc", min_role="manager", min_level=99)),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    _ = user
    return util.common.convert_to_serializable(service.update(assay_id=assay_id, payload=payload))


@router.patch("/api/v1/admin/aspc/{assay_id}/status", response_model=AdminMutationPayload, summary="Toggle assay config status")
def toggle_aspc_mutation(
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="edit_aspc", min_role="manager", min_level=99)),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    _ = user
    return util.common.convert_to_serializable(service.toggle(assay_id=assay_id))


@router.delete("/api/v1/admin/aspc/{assay_id}", response_model=AdminMutationPayload, summary="Delete assay config")
def delete_aspc_mutation(
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="delete_aspc", min_role="admin", min_level=99999)),
    service: AdminAspcService = Depends(get_admin_aspc_service),
):
    _ = user
    return util.common.convert_to_serializable(service.delete(assay_id=assay_id))


@router.get("/api/v1/admin/samples", response_model=AdminSamplesListPayload)
def list_admin_samples_read(
    search: str = Query(default=""),
    user: ApiUser = Depends(require_access(permission="view_sample_global", min_role="developer", min_level=9999)),
    service: AdminSampleService = Depends(get_admin_sample_service),
):
    return util.common.convert_to_serializable(service.list_payload(assays=user.assays, search=search))


@router.get("/api/v1/admin/samples/{sample_id}/context", response_model=AdminSampleContextPayload)
def admin_sample_context_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="developer", min_level=9999)),
    service: AdminSampleService = Depends(get_admin_sample_service),
):
    _ = user
    return util.common.convert_to_serializable(service.context_payload(sample_id=sample_id))


@router.put("/api/v1/admin/samples/{sample_id}", response_model=AdminMutationPayload, summary="Update admin sample")
def update_sample_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="developer", min_level=9999)),
    service: AdminSampleService = Depends(get_admin_sample_service),
):
    return util.common.convert_to_serializable(
        service.update(sample_id=sample_id, payload=payload, actor_username=user.username)
    )


@router.delete("/api/v1/admin/samples/{sample_id}", response_model=AdminMutationPayload, summary="Delete admin sample")
def delete_sample_mutation(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="delete_sample_global", min_role="developer", min_level=9999)),
    service: AdminSampleService = Depends(get_admin_sample_service),
):
    _ = user
    return util.common.convert_to_serializable(service.delete(sample_id=sample_id))


@router.post("/api/v1/admin/schemas", response_model=AdminMutationPayload, status_code=201, summary="Create schema")
def create_schema_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_schema", min_role="developer", min_level=9999)),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    return util.common.convert_to_serializable(
        service.create(payload=payload, actor_username=user.username)
    )


@router.get("/api/v1/admin/schemas", response_model=AdminSchemasListPayload)
def list_schemas_read(
    user: ApiUser = Depends(require_access(permission="view_schema", min_role="developer", min_level=9999)),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    _ = user
    return util.common.convert_to_serializable(service.list_payload())


@router.get("/api/v1/admin/schemas/{schema_id}/context", response_model=AdminSchemaContextPayload)
def schema_context_read(
    schema_id: str,
    user: ApiUser = Depends(require_access(permission="view_schema", min_role="developer", min_level=9999)),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    _ = user
    return util.common.convert_to_serializable(service.context_payload(schema_id=schema_id))


@router.put("/api/v1/admin/schemas/{schema_id}", response_model=AdminMutationPayload, summary="Update schema")
def update_schema_mutation(
    schema_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_schema", min_role="developer", min_level=9999)),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    return util.common.convert_to_serializable(
        service.update(schema_id=schema_id, payload=payload, actor_username=user.username)
    )


@router.patch("/api/v1/admin/schemas/{schema_id}/status", response_model=AdminMutationPayload, summary="Toggle schema status")
def toggle_schema_mutation(
    schema_id: str,
    user: ApiUser = Depends(require_access(permission="edit_schema", min_role="developer", min_level=9999)),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    _ = user
    return util.common.convert_to_serializable(service.toggle(schema_id=schema_id))


@router.delete("/api/v1/admin/schemas/{schema_id}", response_model=AdminMutationPayload, summary="Delete schema")
def delete_schema_mutation(
    schema_id: str,
    user: ApiUser = Depends(require_access(permission="delete_schema", min_role="admin", min_level=99999)),
    service: AdminSchemaService = Depends(get_admin_schema_service),
):
    _ = user
    return util.common.convert_to_serializable(service.delete(schema_id=schema_id))
