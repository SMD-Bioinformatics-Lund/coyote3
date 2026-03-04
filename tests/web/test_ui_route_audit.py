"""UI route boundary and smoke tests."""

from __future__ import annotations

import ast
from pathlib import Path

import coyote
from coyote import init_app
from coyote.services.api_client.api_client import CoyoteApiClient
from coyote.services.api_client.base import ApiPayload


def _view_modules() -> list[Path]:
    return sorted(Path("coyote/blueprints").glob("*/views*.py"))


def test_ui_views_do_not_import_api_core_or_infra():
    offenders: list[str] = []
    for module_path in _view_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("api.core") or alias.name.startswith("api.infra"):
                        offenders.append(f"{module_path}:{alias.name}")
            if isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if base.startswith("api.core") or base.startswith("api.infra"):
                    offenders.append(f"{module_path}:{base}")
    assert not offenders, "UI route modules must stay API-client boundary only:\n" + "\n".join(
        offenders
    )


def test_ui_route_smoke_with_stubbed_api(monkeypatch):
    def _payload(value: dict) -> ApiPayload:
        return ApiPayload(value)

    def _schema_payload(schema_id: str, field_name: str = "name") -> dict:
        return {
            "_id": schema_id,
            "version": 1,
            "sections": {"general": [field_name]},
            "fields": {
                field_name: {
                    "label": field_name.replace("_", " ").title(),
                    "default": "",
                    "readonly": False,
                    "display_type": "text",
                    "placeholder": "",
                    "required": False,
                    "data_type": "str",
                }
            },
        }

    def _fake_get(self, path, headers=None, params=None):  # noqa: ARG001
        if "/admin/users/" in path and path.endswith("/context"):
            schema = _schema_payload("schema-user", "username")
            return _payload(
                {
                    "user_doc": {"_id": "user1", "username": "user1", "role": "admin"},
                    "schema_payload": schema,
                    "role_map": {"admin": {"permissions": [], "deny_permissions": []}},
                    "assay_group_map": {},
                }
            )
        if "/admin/roles/" in path and path.endswith("/context"):
            schema = _schema_payload("schema-role", "name")
            return _payload({"role": {"_id": "role1", "name": "role1"}, "schema_payload": schema})
        if "/admin/permissions/" in path and path.endswith("/context"):
            schema = _schema_payload("schema-perm", "permission_name")
            return _payload(
                {
                    "permission": {"_id": "perm.read", "permission_name": "perm.read"},
                    "schema_payload": schema,
                }
            )
        if "/admin/asp/" in path and path.endswith("/context"):
            schema = _schema_payload("schema-asp", "assay_name")
            return _payload(
                {"panel": {"_id": "asp1", "assay_name": "asp1"}, "schema_payload": schema}
            )
        if "/admin/aspc/" in path and path.endswith("/context"):
            schema = _schema_payload("schema-aspc", "assay_name")
            return _payload(
                {
                    "assay_config": {"_id": "asp1:production", "assay_name": "asp1"},
                    "schema_payload": schema,
                }
            )
        if "/admin/genelists/" in path and path.endswith("/context"):
            schema = _schema_payload("schema-isgl", "name")
            return _payload(
                {
                    "genelist": {"_id": "gl1", "name": "gl1"},
                    "schema_payload": schema,
                    "assay_group_map": {},
                }
            )
        if "/admin/genelists/" in path and path.endswith("/view_context"):
            return _payload(
                {
                    "genelist": {"_id": "gl1", "name": "gl1", "assays": []},
                    "selected_assay": None,
                    "filtered_genes": [],
                    "panel_germline_genes": [],
                }
            )
        if "/admin/samples/" in path and path.endswith("/context"):
            return _payload({"sample": {"_id": "sample1"}})
        if "/admin/schemas/" in path and path.endswith("/context"):
            return _payload({"schema_payload": {"_id": "schema1"}})
        if path.endswith("/internal/roles/levels"):
            return _payload({"role_levels": {}})
        if path.endswith("/dashboard/summary"):
            return _payload(
                {
                    "total_samples": 0,
                    "analysed_samples": 0,
                    "pending_samples": 0,
                    "user_samples_stats": {},
                    "variant_stats": {},
                    "unique_gene_count_all_panels": 0,
                    "assay_gene_stats_grouped": {},
                    "sample_stats": {},
                }
            )
        if path.endswith("/home/samples"):
            return _payload(
                {
                    "live_samples": [],
                    "done_samples": [],
                    "sample_view": "live",
                    "page": 1,
                    "per_page": 30,
                    "has_next_live": False,
                    "has_next_done": False,
                }
            )
        if path.endswith("/common/search/tiered_variants"):
            return _payload(
                {
                    "docs": [],
                    "search_str": "",
                    "search_mode": "gene",
                    "include_annotation_text": False,
                    "tier_stats": {"total": {}, "by_assay": {}},
                    "assays": [],
                    "assay_choices": [],
                }
            )
        if path.endswith("/public/assay-catalog/context"):
            return _payload(
                {
                    "meta": {},
                    "order": [],
                    "modalities": {},
                    "selected_mod": None,
                    "categories": [],
                    "selected_cat": None,
                    "selected_isgl": None,
                    "right": {},
                    "gene_mode": "all",
                    "genes": [],
                    "stats": {},
                }
            )
        if path.endswith("/admin/users"):
            return _payload({"users": [], "roles": {}})
        if path.endswith("/admin/roles"):
            return _payload({"roles": []})
        if path.endswith("/admin/permissions"):
            return _payload({"grouped_permissions": {}})
        if path.endswith("/admin/users/create_context"):
            schema = _schema_payload("schema-user", "username")
            return _payload(
                {
                    "schemas": [schema],
                    "schema_payload": schema,
                    "selected_schema": {"_id": "schema-user"},
                    "role_map": {},
                    "assay_group_map": {},
                }
            )
        if path.endswith("/admin/roles/create_context"):
            schema = _schema_payload("schema-role")
            return _payload(
                {
                    "schemas": [schema],
                    "schema_payload": schema,
                    "selected_schema": {"_id": "schema-role"},
                }
            )
        if path.endswith("/admin/permissions/create_context"):
            schema = _schema_payload("schema-perm")
            return _payload(
                {
                    "schemas": [schema],
                    "schema_payload": schema,
                    "selected_schema": {"_id": "schema-perm"},
                }
            )
        if path.endswith("/admin/samples"):
            return _payload({"samples": []})
        if path.endswith("/admin/asp"):
            return _payload({"panels": []})
        if path.endswith("/admin/asp/create_context"):
            schema = _schema_payload("schema-asp", "assay_name")
            return _payload(
                {
                    "schemas": [schema],
                    "schema_payload": schema,
                    "selected_schema": {"_id": "schema-asp"},
                }
            )
        if path.endswith("/admin/aspc"):
            return _payload({"assay_configs": []})
        if path.endswith("/admin/aspc/create_context"):
            schema = _schema_payload("schema-aspc", "assay_name")
            return _payload(
                {
                    "schemas": [schema],
                    "schema_payload": schema,
                    "selected_schema": {"_id": "schema-aspc"},
                    "prefill_map": {},
                }
            )
        if path.endswith("/admin/genelists"):
            return _payload({"genelists": []})
        if path.endswith("/admin/genelists/create_context"):
            schema = _schema_payload("schema-isgl", "name")
            return _payload(
                {
                    "schemas": [schema],
                    "schema_payload": schema,
                    "selected_schema": {"_id": "schema-isgl"},
                    "assay_group_map": {},
                }
            )
        if path.endswith("/admin/schemas"):
            return _payload({"schemas": []})
        return _payload({})

    def _fake_post(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        if path.endswith("/toggle"):
            return _payload({"meta": {"is_active": True}})
        return _payload({})

    monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)
    monkeypatch.setattr(CoyoteApiClient, "get_json", _fake_get)
    monkeypatch.setattr(CoyoteApiClient, "post_json", _fake_post)

    app = init_app(testing=True)
    client = app.test_client()

    paths = [
        "/admin/",
        "/admin/users",
        "/admin/users/new",
        "/admin/users/user1/view",
        "/admin/users/user1/edit",
        "/admin/users/user1/toggle",
        "/admin/roles",
        "/admin/roles/new",
        "/admin/roles/role1/view",
        "/admin/roles/role1/edit",
        "/admin/roles/role1/toggle",
        "/admin/permissions",
        "/admin/permissions/new",
        "/admin/permissions/perm.read/view",
        "/admin/permissions/perm.read/edit",
        "/admin/permissions/perm.read/toggle",
        "/admin/audit",
        "/dashboard/",
        "/admin/manage-samples",
        "/admin/samples/sample1/edit",
        "/admin/asp/manage",
        "/admin/asp/new",
        "/admin/asp/asp1/view",
        "/admin/asp/asp1/edit",
        "/admin/asp/asp1/toggle",
        "/admin/aspc",
        "/admin/aspc/dna/new",
        "/admin/aspc/asp1:production/view",
        "/admin/aspc/asp1:production/edit",
        "/admin/aspc/asp1:production/toggle",
        "/admin/genelists",
        "/admin/genelists/new",
        "/admin/genelists/gl1/view",
        "/admin/genelists/gl1/edit",
        "/admin/genelists/gl1/toggle",
        "/admin/schemas",
        "/admin/schemas/new",
        "/admin/schemas/schema1/edit",
        "/admin/schemas/schema1/toggle",
        "/public/assay-catalog",
        "/search/tiered_variants",
        "/samples",
    ]
    failures: list[str] = []
    for path in paths:
        response = client.get(path)
        if response.status_code >= 500:
            failures.append(f"{path} -> {response.status_code}")

    assert not failures, "UI smoke route(s) returned 500:\n" + "\n".join(failures)


def test_admin_endpoints_restored(monkeypatch):
    monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)

    app = init_app(testing=True)
    endpoints = set(app.view_functions.keys())
    expected = {
        "admin_bp.all_samples",
        "admin_bp.create_user",
        "admin_bp.create_role",
        "admin_bp.create_permission",
        "admin_bp.manage_assay_panels",
        "admin_bp.create_assay_panel",
        "admin_bp.assay_configs",
        "admin_bp.create_dna_assay_config",
        "admin_bp.create_rna_assay_config",
        "admin_bp.manage_genelists",
        "admin_bp.create_genelist",
        "admin_bp.schemas",
        "admin_bp.create_schema",
    }
    missing = sorted(expected - endpoints)
    assert not missing, "Expected admin endpoints missing:\n" + "\n".join(missing)


def test_admin_create_templates_use_correct_schema_switch_routes():
    assert "admin_bp.create_role" in Path(
        "coyote/blueprints/admin/templates/roles/create_role.html"
    ).read_text(encoding="utf-8")
    assert "admin_bp.create_permission" in Path(
        "coyote/blueprints/admin/templates/permissions/create_permission.html"
    ).read_text(encoding="utf-8")
    assert "admin_bp.create_genelist" in Path(
        "coyote/blueprints/admin/templates/isgl/create_isgl.html"
    ).read_text(encoding="utf-8")
