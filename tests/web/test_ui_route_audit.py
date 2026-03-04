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

    def _fake_get(self, path, headers=None, params=None):  # noqa: ARG001
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
        return _payload({})

    def _fake_post(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        return _payload({})

    monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)
    monkeypatch.setattr(CoyoteApiClient, "get_json", _fake_get)
    monkeypatch.setattr(CoyoteApiClient, "post_json", _fake_post)

    app = init_app(testing=True)
    client = app.test_client()

    paths = [
        "/admin/",
        "/admin/users",
        "/admin/roles",
        "/admin/permissions",
        "/admin/audit",
        "/dashboard/",
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
