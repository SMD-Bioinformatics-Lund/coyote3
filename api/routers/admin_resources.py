"""Canonical router for remaining admin resource endpoints."""

from __future__ import annotations

from copy import deepcopy

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
from api.core.admin.sample_deletion import SampleDeletionService, delete_all_sample_traces
from api.extensions import store, util
from api.http import api_error as _api_error
from api.repositories.admin_repository import AdminRepository as MongoAdminRouteRepository
from api.repositories.admin_repository import AdminSampleDeletionRepository as MongoAdminSampleDeletionRepository
from api.runtime import app as runtime_app, current_username
from api.security.access import ApiUser, require_access

router = APIRouter(tags=["admin-resources"])

_admin_repo_instance: MongoAdminRouteRepository | None = None

if not hasattr(util, "common") or not hasattr(util, "admin"):
    util.init_util()


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


def _admin_repo() -> MongoAdminRouteRepository:
    global _admin_repo_instance
    from api.infra.repositories import admin_route_mongo

    admin_route_mongo.store = store
    if _admin_repo_instance is None:
        _admin_repo_instance = MongoAdminRouteRepository()
    return _admin_repo_instance


def _active_flag(doc: dict | None) -> bool:
    if not isinstance(doc, dict):
        return False
    return bool(doc.get("is_active"))


def _as_dict_rows(items: list[dict]) -> list[dict]:
    return [dict(item) for item in items if isinstance(item, dict)]


def _permission_policy_options() -> list[dict]:
    permission_policies = _admin_repo().permissions_handler.get_all_permissions(is_active=True)
    return [
        {
            "value": p.get("permission_id"),
            "label": p.get("label", p.get("permission_id")),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]


def _role_map() -> dict[str, dict]:
    all_roles = _admin_repo().roles_handler.get_all_roles()
    return {
        role["role_id"]: {
            "permissions": role.get("permissions", []),
            "deny_permissions": role.get("deny_permissions", []),
            "level": role.get("level", 0),
        }
        for role in all_roles
    }


def _assay_group_map() -> dict[str, list[dict]]:
    assay_groups_panels = _admin_repo().asp_handler.get_all_asps()
    return util.common.create_assay_group_map(assay_groups_panels)


def _sample_deletion_service() -> type[SampleDeletionService]:
    if not SampleDeletionService.has_repository():
        SampleDeletionService.set_repository(MongoAdminSampleDeletionRepository())
    return SampleDeletionService


@router.post("/api/v1/admin/asp/create", response_model=AdminMutationPayload)
def create_asp_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_asp", min_role="manager", min_level=99)),
):
    _ = user
    config = payload.get("config", {})
    if not config:
        raise _api_error(400, "Missing panel config payload")
    config.setdefault("is_active", True)
    config["asp_id"] = config.get("asp_id") or config.get("_id") or config.get("assay_name")
    _admin_repo().asp_handler.create_asp(config)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="asp", resource_id=str(config.get("asp_id", "unknown")), action="create")
    )


@router.get("/api/v1/admin/asp", response_model=AdminPanelsListPayload)
def list_asp_read(user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9))):
    _ = user
    panels = _as_dict_rows(_admin_repo().asp_handler.get_all_asps())
    return util.common.convert_to_serializable({"panels": panels})


@router.get("/api/v1/admin/asp/create_context", response_model=AdminPanelCreateContextPayload)
def create_asp_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_asp", min_role="manager", min_level=99)),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="asp_schema",
        schema_category="ASP",
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, "No active panel schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise _api_error(404, "Selected schema not found")

    schema = deepcopy(selected_schema)
    schema["fields"]["created_by"]["default"] = current_username(default=user.username)
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_username(default=user.username)
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    return util.common.convert_to_serializable({"schemas": active_schemas, "selected_schema": selected_schema, "schema": schema})


@router.get("/api/v1/admin/asp/{assay_panel_id}/context", response_model=AdminPanelContextPayload)
def asp_context_read(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="view_asp", min_role="user", min_level=9)),
):
    _ = user
    panel = _admin_repo().asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")

    schema = _admin_repo().schema_handler.get_schema(panel.get("schema_name", "ASP-Schema"))
    if not schema:
        raise _api_error(404, "Schema not found for panel")

    return util.common.convert_to_serializable({"panel": panel, "schema": schema})


@router.post("/api/v1/admin/asp/{assay_panel_id}/update", response_model=AdminMutationPayload)
def update_asp_mutation(
    assay_panel_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_asp", min_role="manager", min_level=99)),
):
    _ = user
    panel = _admin_repo().asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")
    updated = payload.get("config", {})
    if not updated:
        raise _api_error(400, "Missing panel config payload")
    updated["asp_id"] = panel.get("asp_id", assay_panel_id)
    updated["_id"] = panel.get("_id")
    _admin_repo().asp_handler.update_asp(assay_panel_id, updated)
    return util.common.convert_to_serializable(_mutation_payload("admin", resource="asp", resource_id=assay_panel_id, action="update"))


@router.post("/api/v1/admin/asp/{assay_panel_id}/toggle", response_model=AdminMutationPayload)
def toggle_asp_mutation(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="edit_asp", min_role="manager", min_level=99)),
):
    _ = user
    panel = _admin_repo().asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")
    new_status = not _active_flag(panel)
    _admin_repo().asp_handler.toggle_asp_active(assay_panel_id, new_status)
    result = _mutation_payload("admin", resource="asp", resource_id=assay_panel_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/admin/asp/{assay_panel_id}/delete", response_model=AdminMutationPayload)
def delete_asp_mutation(
    assay_panel_id: str,
    user: ApiUser = Depends(require_access(permission="delete_asp", min_role="admin", min_level=99999)),
):
    _ = user
    panel = _admin_repo().asp_handler.get_asp(assay_panel_id)
    if not panel:
        raise _api_error(404, "Panel not found")
    _admin_repo().asp_handler.delete_asp(assay_panel_id)
    return util.common.convert_to_serializable(_mutation_payload("admin", resource="asp", resource_id=assay_panel_id, action="delete"))


@router.post("/api/v1/admin/genelists/create", response_model=AdminMutationPayload)
def create_genelist_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_isgl", min_role="manager", min_level=99)),
):
    _ = user
    config = payload.get("config", {})
    if not config:
        raise _api_error(400, "Missing genelist config payload")
    config.setdefault("is_active", True)
    config["isgl_id"] = config.get("isgl_id") or config.get("_id") or config.get("name")
    _admin_repo().isgl_handler.create_isgl(config)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="genelist", resource_id=str(config.get("isgl_id", "unknown")), action="create")
    )


@router.get("/api/v1/admin/genelists", response_model=AdminGenelistsListPayload)
def list_genelists_read(user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9))):
    _ = user
    genelists = _as_dict_rows(_admin_repo().isgl_handler.get_all_isgl())
    return util.common.convert_to_serializable({"genelists": genelists})


@router.get("/api/v1/admin/genelists/create_context", response_model=AdminGenelistCreateContextPayload)
def create_genelist_context_read(
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_isgl", min_role="manager", min_level=99)),
):
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="isgl_config",
        schema_category="ISGL",
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, "No active genelist schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise _api_error(404, "Genelist schema not found")

    schema = deepcopy(selected_schema)
    schema["fields"]["assay_groups"]["options"] = _admin_repo().asp_handler.get_all_asp_groups()
    schema["fields"]["created_by"]["default"] = current_username(default=user.username)
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_username(default=user.username)
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    return util.common.convert_to_serializable(
        {"schemas": active_schemas, "selected_schema": selected_schema, "schema": schema, "assay_group_map": _assay_group_map()}
    )


@router.get("/api/v1/admin/genelists/{genelist_id}/context", response_model=AdminGenelistContextPayload)
def genelist_context_read(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
):
    _ = user
    genelist = _admin_repo().isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")

    schema = _admin_repo().schema_handler.get_schema(genelist.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema not found for genelist")

    schema = deepcopy(schema)
    schema["fields"]["assay_groups"]["options"] = _admin_repo().asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["default"] = genelist.get("assay_groups", [])
    schema["fields"]["assays"]["default"] = genelist.get("assays", [])

    return util.common.convert_to_serializable(
        {"genelist": genelist, "schema": schema, "assay_group_map": _assay_group_map()}
    )


@router.get("/api/v1/admin/genelists/{genelist_id}/view_context", response_model=AdminGenelistViewContextPayload)
def genelist_view_context_read(
    genelist_id: str,
    assay: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="view_isgl", min_role="user", min_level=9)),
):
    _ = user
    genelist = _admin_repo().isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")

    all_genes = genelist.get("genes", [])
    assays = genelist.get("assays", [])
    filtered_genes = all_genes
    panel_germline_genes: list[str] = []

    if assay and assay in assays:
        panel = _admin_repo().asp_handler.get_asp(assay)
        panel_genes = panel.get("covered_genes", []) if panel else []
        panel_germline_genes = panel.get("germline_genes", []) if panel else []
        filtered_genes = sorted(set(all_genes).intersection(panel_genes))

    return util.common.convert_to_serializable(
        {"genelist": genelist, "selected_assay": assay, "filtered_genes": filtered_genes, "panel_germline_genes": panel_germline_genes}
    )


@router.post("/api/v1/admin/genelists/{genelist_id}/update", response_model=AdminMutationPayload)
def update_genelist_mutation(
    genelist_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_isgl", min_role="manager", min_level=99)),
):
    _ = user
    genelist = _admin_repo().isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")
    updated = payload.get("config", {})
    if not updated:
        raise _api_error(400, "Missing genelist config payload")
    updated["isgl_id"] = genelist.get("isgl_id", genelist_id)
    updated["_id"] = genelist.get("_id")
    _admin_repo().isgl_handler.update_isgl(genelist_id, updated)
    return util.common.convert_to_serializable(_mutation_payload("admin", resource="genelist", resource_id=genelist_id, action="update"))


@router.post("/api/v1/admin/genelists/{genelist_id}/toggle", response_model=AdminMutationPayload)
def toggle_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="edit_isgl", min_role="manager", min_level=99)),
):
    _ = user
    genelist = _admin_repo().isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")
    new_status = not _active_flag(genelist)
    _admin_repo().isgl_handler.toggle_isgl_active(genelist_id, new_status)
    result = _mutation_payload("admin", resource="genelist", resource_id=genelist_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/admin/genelists/{genelist_id}/delete", response_model=AdminMutationPayload)
def delete_genelist_mutation(
    genelist_id: str,
    user: ApiUser = Depends(require_access(permission="delete_isgl", min_role="admin", min_level=99999)),
):
    _ = user
    genelist = _admin_repo().isgl_handler.get_isgl(genelist_id)
    if not genelist:
        raise _api_error(404, "Genelist not found")
    _admin_repo().isgl_handler.delete_isgl(genelist_id)
    return util.common.convert_to_serializable(_mutation_payload("admin", resource="genelist", resource_id=genelist_id, action="delete"))


@router.get("/api/v1/admin/aspc", response_model=AdminAspcListPayload)
def list_aspc_read(user: ApiUser = Depends(require_access(permission="view_aspc", min_role="user", min_level=9))):
    _ = user
    assay_configs = _as_dict_rows(list(_admin_repo().aspc_handler.get_all_aspc()))
    return util.common.convert_to_serializable({"assay_configs": assay_configs})


@router.get("/api/v1/admin/aspc/create_context", response_model=AdminAspcCreateContextPayload)
def create_aspc_context_read(
    category: str = Query(default="DNA"),
    schema_id: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="create_aspc", min_role="manager", min_level=99)),
):
    schema_category = str(category or "DNA").upper()
    active_schemas = _admin_repo().schema_handler.get_schemas_by_category_type(
        schema_type="asp_config",
        schema_category=schema_category,
        is_active=True,
    )
    if not active_schemas:
        raise _api_error(400, f"No active {schema_category} schemas found")

    selected_id = schema_id or active_schemas[0]["_id"]
    selected_schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not selected_schema:
        raise _api_error(404, "Selected schema not found")

    schema = deepcopy(selected_schema)
    assay_panels = _admin_repo().asp_handler.get_all_asps(is_active=True)
    prefill_map: dict[str, dict] = {}
    valid_assay_ids: list[str] = []

    for panel in assay_panels:
        if panel.get("asp_category") == schema_category:
            envs = _admin_repo().aspc_handler.get_available_assay_envs(panel["_id"], schema["fields"]["environment"]["options"])
            if envs:
                valid_assay_ids.append(panel["_id"])
                prefill_map[panel["_id"]] = {
                    "display_name": panel.get("display_name"),
                    "asp_group": panel.get("asp_group"),
                    "asp_category": panel.get("asp_category"),
                    "platform": panel.get("platform"),
                    "environment": envs,
                }

    schema["fields"]["assay_name"]["options"] = valid_assay_ids
    if schema_category == "DNA" and "vep_consequences" in schema.get("fields", {}):
        schema["fields"]["vep_consequences"]["options"] = list(runtime_app.config.get("CONSEQ_TERMS_MAPPER", {}).keys())
    schema["fields"]["created_by"]["default"] = current_username(default=user.username)
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_username(default=user.username)
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    return util.common.convert_to_serializable(
        {"category": schema_category, "schemas": active_schemas, "selected_schema": selected_schema, "schema": schema, "prefill_map": prefill_map}
    )


@router.get("/api/v1/admin/aspc/{assay_id}/context", response_model=AdminAspcContextPayload)
def aspc_context_read(
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="view_aspc", min_role="user", min_level=9)),
):
    _ = user
    assay_config = _admin_repo().aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        raise _api_error(404, "Assay config not found")

    schema = _admin_repo().schema_handler.get_schema(assay_config.get("schema_name"))
    if not schema:
        raise _api_error(404, "Schema for this assay config is missing")
    schema = deepcopy(schema)
    if "vep_consequences" in schema.get("fields", {}):
        schema["fields"]["vep_consequences"]["options"] = list(runtime_app.config.get("CONSEQ_TERMS_MAPPER", {}).keys())

    return util.common.convert_to_serializable({"assay_config": assay_config, "schema": schema})


@router.post("/api/v1/admin/aspc/create", response_model=AdminMutationPayload)
def create_aspc_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_aspc", min_role="manager", min_level=99)),
):
    _ = user
    config = payload.get("config", {})
    if not config:
        raise _api_error(400, "Missing assay config payload")
    config.setdefault("is_active", True)
    config["aspc_id"] = config.get("aspc_id") or config.get("_id") or f"{str(config.get('assay_name', '')).strip()}:{str(config.get('environment', '')).strip().lower()}"
    config["_id"] = config["aspc_id"]
    existing_config = _admin_repo().aspc_handler.get_aspc_with_id(config.get("aspc_id"))
    if existing_config:
        raise _api_error(409, "Assay config already exists")
    _admin_repo().aspc_handler.create_aspc(config)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="aspc", resource_id=str(config.get("aspc_id", "unknown")), action="create")
    )


@router.post("/api/v1/admin/aspc/{assay_id}/update", response_model=AdminMutationPayload)
def update_aspc_mutation(
    assay_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_aspc", min_role="manager", min_level=99)),
):
    _ = user
    assay_config = _admin_repo().aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        raise _api_error(404, "Assay config not found")
    updated_config = payload.get("config", {})
    if not updated_config:
        raise _api_error(400, "Missing assay config payload")
    updated_config["aspc_id"] = assay_config.get("aspc_id", assay_id)
    updated_config["_id"] = assay_config.get("_id", assay_id)
    _admin_repo().aspc_handler.update_aspc(assay_id, updated_config)
    return util.common.convert_to_serializable(_mutation_payload("admin", resource="aspc", resource_id=assay_id, action="update"))


@router.post("/api/v1/admin/aspc/{assay_id}/toggle", response_model=AdminMutationPayload)
def toggle_aspc_mutation(
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="edit_aspc", min_role="manager", min_level=99)),
):
    _ = user
    assay_config = _admin_repo().aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        raise _api_error(404, "Assay config not found")
    new_status = not _active_flag(assay_config)
    _admin_repo().aspc_handler.toggle_aspc_active(assay_id, new_status)
    result = _mutation_payload("admin", resource="aspc", resource_id=assay_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/admin/aspc/{assay_id}/delete", response_model=AdminMutationPayload)
def delete_aspc_mutation(
    assay_id: str,
    user: ApiUser = Depends(require_access(permission="delete_aspc", min_role="admin", min_level=99999)),
):
    _ = user
    assay_config = _admin_repo().aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        raise _api_error(404, "Assay config not found")
    _admin_repo().aspc_handler.delete_aspc(assay_id)
    return util.common.convert_to_serializable(_mutation_payload("admin", resource="aspc", resource_id=assay_id, action="delete"))


@router.get("/api/v1/admin/samples", response_model=AdminSamplesListPayload)
def list_admin_samples_read(
    search: str = Query(default=""),
    user: ApiUser = Depends(require_access(permission="view_sample_global", min_role="developer", min_level=9999)),
):
    samples = list(_admin_repo().sample_handler.get_all_samples(user.assays, None, search))
    return util.common.convert_to_serializable({"samples": samples})


@router.get("/api/v1/admin/samples/{sample_id}/context", response_model=AdminSampleContextPayload)
def admin_sample_context_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="developer", min_level=9999)),
):
    _ = user
    sample_doc = _admin_repo().sample_handler.get_sample(sample_id)
    if not sample_doc:
        raise _api_error(404, "Sample not found")
    return util.common.convert_to_serializable({"sample": sample_doc})


@router.post("/api/v1/admin/samples/{sample_id}/update", response_model=AdminMutationPayload)
def update_sample_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="developer", min_level=9999)),
):
    sample_doc = _admin_repo().sample_handler.get_sample(sample_id)
    if not sample_doc:
        raise _api_error(404, "Sample not found")
    sample_obj = sample_doc.get("_id")
    updated_sample = payload.get("sample", {})
    if not updated_sample:
        raise _api_error(400, "Missing sample payload")
    updated_sample["updated_on"] = util.common.utc_now()
    updated_sample["updated_by"] = current_username(default=user.username)
    updated_sample = util.admin.restore_objectids(deepcopy(updated_sample))
    updated_sample["_id"] = sample_obj
    _admin_repo().sample_handler.update_sample(sample_obj, updated_sample)
    return util.common.convert_to_serializable(
        _mutation_payload("admin", resource="sample", resource_id=str(sample_obj), action="update")
    )


@router.post("/api/v1/admin/samples/{sample_id}/delete", response_model=AdminMutationPayload)
def delete_sample_mutation(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="delete_sample_global", min_role="developer", min_level=9999)),
):
    _sample_deletion_service()
    sample_name = _admin_repo().sample_handler.get_sample_name(sample_id)
    if not sample_name:
        raise _api_error(404, "Sample not found")
    deletion_summary = delete_all_sample_traces(sample_id)
    result = _mutation_payload("admin", resource="sample", resource_id=sample_id, action="delete")
    result["meta"]["sample_name"] = deletion_summary.get("sample_name") or sample_name
    result["meta"]["results"] = deletion_summary.get("results", [])
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/admin/schemas/create", response_model=AdminMutationPayload)
def create_schema_mutation(
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="create_schema", min_role="developer", min_level=9999)),
):
    schema_doc = payload.get("schema", {})
    schema_doc["_id"] = schema_doc.get("schema_name")
    schema_doc["schema_id"] = schema_doc.get("schema_name")
    schema_doc.setdefault("is_active", True)
    schema_doc["created_on"] = util.common.utc_now()
    schema_doc["created_by"] = current_username(default=user.username)
    schema_doc["updated_on"] = util.common.utc_now()
    schema_doc["updated_by"] = current_username(default=user.username)
    _admin_repo().schema_handler.create_schema(schema_doc)
    return util.common.convert_to_serializable(_mutation_payload("admin", resource="schema", resource_id=schema_doc["_id"], action="create"))


@router.get("/api/v1/admin/schemas", response_model=AdminSchemasListPayload)
def list_schemas_read(
    user: ApiUser = Depends(require_access(permission="view_schema", min_role="developer", min_level=9999)),
):
    _ = user
    schemas = _as_dict_rows(list(_admin_repo().schema_handler.get_all_schemas()))
    return util.common.convert_to_serializable({"schemas": schemas})


@router.get("/api/v1/admin/schemas/{schema_id}/context", response_model=AdminSchemaContextPayload)
def schema_context_read(
    schema_id: str,
    user: ApiUser = Depends(require_access(permission="view_schema", min_role="developer", min_level=9999)),
):
    _ = user
    schema_doc = _admin_repo().schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    return util.common.convert_to_serializable({"schema": schema_doc})


@router.post("/api/v1/admin/schemas/{schema_id}/update", response_model=AdminMutationPayload)
def update_schema_mutation(
    schema_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_schema", min_role="developer", min_level=9999)),
):
    schema_doc = _admin_repo().schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    updated_schema = payload.get("schema", {})
    updated_schema["_id"] = schema_doc["_id"]
    updated_schema["schema_id"] = schema_doc.get("schema_id", schema_id)
    updated_schema["updated_on"] = util.common.utc_now()
    updated_schema["updated_by"] = current_username(default=user.username)
    updated_schema["version"] = schema_doc.get("version", 1) + 1
    _admin_repo().schema_handler.update_schema(schema_id, updated_schema)
    return util.common.convert_to_serializable(_mutation_payload("admin", resource="schema", resource_id=schema_id, action="update"))


@router.post("/api/v1/admin/schemas/{schema_id}/toggle", response_model=AdminMutationPayload)
def toggle_schema_mutation(
    schema_id: str,
    user: ApiUser = Depends(require_access(permission="edit_schema", min_role="developer", min_level=9999)),
):
    _ = user
    schema_doc = _admin_repo().schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    new_status = not _active_flag(schema_doc)
    _admin_repo().schema_handler.toggle_schema_active(schema_id, new_status)
    result = _mutation_payload("admin", resource="schema", resource_id=schema_id, action="toggle")
    result["meta"]["is_active"] = new_status
    return util.common.convert_to_serializable(result)


@router.post("/api/v1/admin/schemas/{schema_id}/delete", response_model=AdminMutationPayload)
def delete_schema_mutation(
    schema_id: str,
    user: ApiUser = Depends(require_access(permission="delete_schema", min_role="admin", min_level=99999)),
):
    _ = user
    schema_doc = _admin_repo().schema_handler.get_schema(schema_id)
    if not schema_doc:
        raise _api_error(404, "Schema not found")
    _admin_repo().schema_handler.delete_schema(schema_id)
    return util.common.convert_to_serializable(_mutation_payload("admin", resource="schema", resource_id=schema_id, action="delete"))
