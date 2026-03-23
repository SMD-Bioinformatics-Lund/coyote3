"""UI route boundary and smoke tests."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import coyote
from coyote import init_app
from coyote.services.api_client.api_client import CoyoteApiClient
from coyote.services.api_client.base import ApiPayload


def _view_modules() -> list[Path]:
    """View modules.

    Returns:
            The  view modules result.
    """
    return sorted(Path("coyote/blueprints").glob("*/views*.py"))


def _literal_url_for_endpoints_from_python() -> list[tuple[str, int, str]]:
    """Literal url for endpoints from python.

    Returns:
            The  literal url for endpoints from python result.
    """
    calls: list[tuple[str, int, str]] = []
    for py_file in sorted(Path("coyote").rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "url_for":
                continue
            if not node.args:
                continue
            endpoint_node = node.args[0]
            if isinstance(endpoint_node, ast.Constant) and isinstance(endpoint_node.value, str):
                calls.append((str(py_file), node.lineno, endpoint_node.value))
    return calls


def _literal_url_for_endpoints_from_templates() -> list[tuple[str, int, str]]:
    """Literal url for endpoints from templates.

    Returns:
            The  literal url for endpoints from templates result.
    """
    calls: list[tuple[str, int, str]] = []
    pattern = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")
    for html_file in sorted(Path("coyote").rglob("*.html")):
        content = html_file.read_text(encoding="utf-8")
        for match in pattern.finditer(content):
            line = 1 + content.count("\n", 0, match.start())
            calls.append((str(html_file), line, match.group(1)))
    return calls


def test_ui_views_do_not_import_api_core_or_infra():
    """Test ui views do not import api core or infra.

    Returns:
        The function result.
    """
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
    """Test ui route smoke with stubbed api.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """

    def _payload(value: dict) -> ApiPayload:
        """Payload.

        Args:
                value: Value.

        Returns:
                The  payload result.
        """
        return ApiPayload(value)

    def _schema(schema_id: str, field_name: str = "name") -> dict:
        """Schema.

        Args:
                schema_id: Schema id.
                field_name: Field name. Optional argument.

        Returns:
                The  schema result.
        """
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
        """Fake get.

        Args:
                path: Path.
                headers: Headers. Optional argument.
                params: Params. Optional argument.

        Returns:
                The  fake get result.
        """
        if "/users/" in path and path.endswith("/context"):
            schema = _schema("schema-user", "username")
            return _payload(
                {
                    "user_doc": {"_id": "user1", "username": "user1", "role": "admin"},
                    "schema": schema,
                    "role_map": {"admin": {"permissions": [], "deny_permissions": []}},
                    "assay_group_map": {},
                }
            )
        if "/roles/" in path and path.endswith("/context"):
            schema = _schema("schema-role", "name")
            return _payload({"role": {"_id": "role1", "name": "role1"}, "schema": schema})
        if "/permissions/" in path and path.endswith("/context"):
            schema = _schema("schema-perm", "permission_name")
            return _payload(
                {
                    "permission": {"_id": "perm.read", "permission_name": "perm.read"},
                    "schema": schema,
                }
            )
        if "/resources/asp/" in path and path.endswith("/context"):
            schema = _schema("schema-asp", "assay_name")
            return _payload({"panel": {"_id": "asp1", "assay_name": "asp1"}, "schema": schema})
        if "/resources/aspc/" in path and path.endswith("/context"):
            schema = _schema("schema-aspc", "assay_name")
            return _payload(
                {
                    "assay_config": {"_id": "asp1:production", "assay_name": "asp1"},
                    "schema": schema,
                }
            )
        if "/resources/genelists/" in path and path.endswith("/context"):
            schema = _schema("schema-isgl", "name")
            return _payload(
                {
                    "genelist": {"_id": "gl1", "name": "gl1"},
                    "schema": schema,
                    "assay_group_map": {},
                }
            )
        if "/resources/genelists/" in path and path.endswith("/view_context"):
            return _payload(
                {
                    "genelist": {"_id": "gl1", "name": "gl1", "assays": []},
                    "selected_assay": None,
                    "filtered_genes": [],
                    "panel_germline_genes": [],
                }
            )
        if "/resources/samples/" in path and path.endswith("/context"):
            return _payload({"sample": {"_id": "sample1"}})
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
        if path.endswith("/api/v1/samples"):
            return _payload(
                {
                    "live_samples": [],
                    "done_samples": [],
                    "sample_view": "all",
                    "profile_scope": "production",
                    "page": 1,
                    "per_page": 30,
                    "live_page": 1,
                    "live_per_page": 30,
                    "done_page": 1,
                    "done_per_page": 30,
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
        if path.endswith("/users"):
            return _payload({"users": [], "roles": {}})
        if path.endswith("/roles"):
            return _payload({"roles": []})
        if path.endswith("/permissions"):
            return _payload({"grouped_permissions": {}})
        if path.endswith("/users/create_context"):
            schema = _schema("schema-user", "username")
            return _payload(
                {
                    "schemas": [schema],
                    "schema": schema,
                    "selected_schema": {"_id": "schema-user"},
                    "role_map": {},
                    "assay_group_map": {},
                }
            )
        if path.endswith("/roles/create_context"):
            schema = _schema("schema-role")
            return _payload(
                {
                    "schemas": [schema],
                    "schema": schema,
                    "selected_schema": {"_id": "schema-role"},
                }
            )
        if path.endswith("/permissions/create_context"):
            schema = _schema("schema-perm")
            return _payload(
                {
                    "schemas": [schema],
                    "schema": schema,
                    "selected_schema": {"_id": "schema-perm"},
                }
            )
        if path.endswith("/resources/samples"):
            return _payload({"samples": []})
        if path.endswith("/resources/asp"):
            return _payload({"panels": []})
        if path.endswith("/resources/asp/create_context"):
            schema = _schema("schema-asp", "assay_name")
            return _payload(
                {
                    "schemas": [schema],
                    "schema": schema,
                    "selected_schema": {"_id": "schema-asp"},
                }
            )
        if path.endswith("/resources/aspc"):
            return _payload({"assay_configs": []})
        if path.endswith("/resources/aspc/create_context"):
            schema = _schema("schema-aspc", "assay_name")
            return _payload(
                {
                    "schemas": [schema],
                    "schema": schema,
                    "selected_schema": {"_id": "schema-aspc"},
                    "prefill_map": {},
                }
            )
        if path.endswith("/resources/genelists"):
            return _payload({"genelists": []})
        if path.endswith("/resources/genelists/create_context"):
            schema = _schema("schema-isgl", "name")
            return _payload(
                {
                    "schemas": [schema],
                    "schema": schema,
                    "selected_schema": {"_id": "schema-isgl"},
                    "assay_group_map": {},
                }
            )
        return _payload({})

    def _fake_post(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        """Fake post.

        Args:
                path: Path.
                headers: Headers. Optional argument.
                params: Params. Optional argument.
                json_body: Json body. Optional argument.

        Returns:
                The  fake post result.
        """
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
    """Test admin endpoints restored.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
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
    }
    missing = sorted(expected - endpoints)
    assert not missing, "Expected admin endpoints missing:\n" + "\n".join(missing)


def test_admin_create_templates_use_correct_schema_switch_routes():
    """Test admin create templates use correct schema switch routes.

    Returns:
        The function result.
    """
    assert "admin_bp.create_role" in Path(
        "coyote/blueprints/admin/templates/roles/create_role.html"
    ).read_text(encoding="utf-8")
    assert "admin_bp.create_permission" in Path(
        "coyote/blueprints/admin/templates/permissions/create_permission.html"
    ).read_text(encoding="utf-8")
    assert "admin_bp.create_genelist" in Path(
        "coyote/blueprints/admin/templates/isgl/create_isgl.html"
    ).read_text(encoding="utf-8")


def test_ui_literal_url_for_endpoints_exist(monkeypatch):
    """Test ui literal url for endpoints exist.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)
    app = init_app(testing=True)
    with app.app_context():
        existing_endpoints = set(app.view_functions.keys())

    missing: list[str] = []
    for source, line, endpoint in (
        _literal_url_for_endpoints_from_python() + _literal_url_for_endpoints_from_templates()
    ):
        if endpoint not in existing_endpoints:
            missing.append(f"{source}:{line} -> {endpoint}")

    assert not missing, "Unknown literal url_for endpoint(s):\n" + "\n".join(sorted(missing))
