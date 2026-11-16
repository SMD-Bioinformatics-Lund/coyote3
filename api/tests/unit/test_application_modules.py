"""Feature gates follow API declarations, retain error contracts and preserve recovery."""

from types import SimpleNamespace

import pytest
from coyote.config.application_modules import APPLICATION_MODULE_BY_KEY
from coyote_api.app import middleware
from coyote_api.app.deps import services
from coyote_api.app.deps.modules import RequireModules
from coyote_api.interfaces.http.registry import ROUTERS, auth_http_exception_handler
from coyote_api.security.access import ApiUser
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient


def api_user():
    """Build a synthetic actor without importing repository-level test fixtures."""
    return ApiUser(
        id="u1",
        username="tester",
        email="tester@example.com",
        fullname="Test User",
        roles=["admin", "superuser"],
        role="admin",
        access_level=99999,
        permissions=["report:preview", "report:create", "role:view", "sample:edit:own"],
        asp_ids=["wgs", "rna_panel"],
        assay_access=[
            {"asp_id": assay, "environments": ["production"]} for assay in ["wgs", "rna_panel"]
        ],
        asp_groups=["dna", "rna"],
        envs=["production"],
        asp_map={"DNA": {"PANEL": {"dna": ["wgs"]}}},
        auth_type=["local"],
    )


@pytest.fixture
def boundary(monkeypatch):
    """Run the real authentication/audit middleware with explicit, mutable availability."""
    disabled = set()
    checked = []
    events, mutations, metrics = [], [], []

    def enabled(key):
        checked.append(key)
        return key not in disabled

    monkeypatch.setattr(
        services, "get_app_controls_service", lambda: SimpleNamespace(module_enabled=enabled)
    )
    monkeypatch.setattr(middleware, "ensure_runtime_initialized", lambda **_: None)
    monkeypatch.setattr(middleware, "resolve_request_user", lambda _request: api_user())
    monkeypatch.setattr(middleware, "emit_request_event", lambda **values: events.append(values))
    monkeypatch.setattr(
        middleware, "emit_mutation_event", lambda **values: mutations.append(values)
    )
    monkeypatch.setattr(middleware, "observe_request", lambda **values: metrics.append(values))
    monkeypatch.setitem(middleware.runtime_app.config, "API_RATE_LIMIT_ENABLED", False)
    monkeypatch.setitem(middleware.runtime_app.config, "API_CSRF_ENABLED", False)
    monkeypatch.setattr(middleware, "_API_LIMITER", None)
    monkeypatch.setattr(middleware, "_API_LIMITER_CFG", None)
    app = FastAPI()
    app.add_exception_handler(HTTPException, auth_http_exception_handler)
    app.middleware("http")(
        middleware.build_authentication_middleware(testing=True, development=False)
    )
    return SimpleNamespace(
        app=app,
        disabled=disabled,
        checked=checked,
        events=events,
        mutations=mutations,
        metrics=metrics,
    )


@pytest.mark.parametrize("key", APPLICATION_MODULE_BY_KEY)
def test_disabled_feature_blocks_services_and_handler_with_existing_503(boundary, key):
    """All features enforce availability independently of route spelling and UI state."""
    boundary.disabled.add(key)

    def service():
        pytest.fail("Disabled features must not open endpoint service operations")

    @boundary.app.get("/api/v1/renamed-workflow", dependencies=[Depends(RequireModules(key))])
    def endpoint(_service=Depends(service)):
        pytest.fail("Disabled feature handler executed")

    with TestClient(boundary.app) as client:
        response = client.get("/api/v1/renamed-workflow")
    payload = response.json()
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "60"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"] == payload["request_id"]
    assert payload["category"] == "module_disabled"
    assert payload["module"] == key
    assert payload["code"] == "service_unavailable"
    assert "temporarily unavailable" in payload["hint"]
    assert len(boundary.events) == len(boundary.metrics) == 1
    assert boundary.events[0]["extra"] == {"kind": "module_disabled", "module": key}


@pytest.mark.parametrize("disabled", ["dna_analysis", "knowledgebases", None])
def test_router_and_endpoint_requirements_are_combined(boundary, disabled):
    """A variant lookup requires both its analysis and knowledgebase feature."""
    router = APIRouter(dependencies=[Depends(RequireModules("dna_analysis"))])

    @router.get("/api/v1/lookup", dependencies=[Depends(RequireModules("knowledgebases"))])
    def endpoint():
        return {"status": "ok"}

    boundary.app.include_router(router)
    if disabled:
        boundary.disabled.add(disabled)
    with TestClient(boundary.app) as client:
        response = client.get("/api/v1/lookup")
    assert response.status_code == (503 if disabled else 200)
    if disabled:
        assert response.json()["module"] == disabled
    else:
        assert set(boundary.checked) == {"dna_analysis", "knowledgebases"}


def test_availability_is_reread_and_url_substrings_do_not_select_features(boundary):
    """Saved availability changes take effect without route-name-based false matches."""
    router = APIRouter(dependencies=[Depends(RequireModules("reports"))])

    @router.get("/api/v1/custom/{identifier}")
    def endpoint(identifier: str):
        return {"identifier": identifier}

    boundary.app.include_router(router)
    boundary.disabled.update({"dna_analysis", "rna_analysis", "reports"})
    with TestClient(boundary.app) as client:
        assert client.get("/api/v1/custom/fusions").status_code == 503
        boundary.disabled.remove("reports")
        assert client.get("/api/v1/custom/biomarkers").status_code == 200
        assert client.get("/api/v1/custom/fusions").status_code == 200
    assert set(boundary.checked) == {"reports"}


def test_blocked_mutation_records_request_failure_without_a_mutation_event(boundary):
    """Moving the gate preserves the previous audit behavior for unexecuted writes."""
    boundary.disabled.add("reports")

    @boundary.app.post("/api/v1/module-action", dependencies=[Depends(RequireModules("reports"))])
    def endpoint():
        pytest.fail("Disabled mutation executed")

    with TestClient(boundary.app) as client:
        assert client.post("/api/v1/module-action").status_code == 503
    assert len(boundary.events) == len(boundary.metrics) == 1
    assert boundary.mutations == []


@pytest.mark.parametrize("root_path,prefix", [("", ""), ("/center", "/center"), ("/center", "")])
def test_authentication_and_csrf_still_precede_module_checks(
    boundary, monkeypatch, root_path, prefix
):
    """Disabled availability does not replace authentication or CSRF failures."""
    boundary.disabled.add("reports")
    boundary.app.root_path = root_path

    @boundary.app.post("/api/v1/protected", dependencies=[Depends(RequireModules("reports"))])
    def endpoint():
        pytest.fail("Protected handler executed")

    with TestClient(boundary.app) as client:
        monkeypatch.setattr(middleware, "resolve_request_user", lambda _request: None)
        assert client.post(f"{prefix}/api/v1/protected").status_code == 401
        monkeypatch.setattr(middleware, "resolve_request_user", lambda _request: api_user())
        monkeypatch.setitem(middleware.runtime_app.config, "API_CSRF_ENABLED", True)
        monkeypatch.setattr(middleware, "validate_request_csrf", lambda _request: False)
        assert client.post(f"{prefix}/api/v1/protected").status_code == 403
        assert boundary.checked == []
        monkeypatch.setattr(middleware, "validate_request_csrf", lambda _request: True)
        assert client.post(f"{prefix}/api/v1/protected").status_code == 503
    assert boundary.checked == ["reports"]


def _required(dependant):
    """Collect effective declarations, including inherited router dependencies."""
    keys = set()
    for dependency in dependant.dependencies:
        if isinstance(dependency.call, RequireModules):
            keys.update(dependency.call.module_keys)
        keys.update(_required(dependency))
    return keys


@pytest.mark.parametrize(
    ("name", "required"),
    [
        ("list_dna_variants", {"dna_analysis"}),
        ("review_dna_biomarkers", {"dna_analysis"}),
        ("coverage_sample_read", {"dna_analysis"}),
        ("create_coverage_blacklist_entry", {"dna_analysis"}),
        ("list_rna_fusions", {"rna_analysis"}),
        ("read_rna_analysis", {"rna_analysis"}),
        ("preview_report", {"reports"}),
        ("show_dna_variant_public_oncokb", {"dna_analysis", "knowledgebases"}),
        ("show_dna_variant_public_clinpgx", {"dna_analysis", "knowledgebases"}),
        ("common_tiered_variant_search_read", {"variant_search"}),
        ("common_tiered_variant_context_read", {"variant_search"}),
        ("ingest_sample_bundle_internal", {"ingest_workspace"}),
        ("public_assay_catalog_matrix_context_read", {"assay_catalog"}),
        ("admin_controls_public_oncokb_refresh", {"knowledgebases"}),
    ],
)
def test_real_api_routes_declare_their_required_features(name, required):
    """The production route registry retains existing gates and covers RNA analysis."""
    route = next(route for entry in ROUTERS for route in entry.router.routes if route.name == name)
    assert _required(route.dependant) == required


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/controls",
        "/api/v1/admin/audit",
        "/api/v1/public/modules",
        "/api/v1/health",
        "/api/v1/auth/sessions",
        "/api/v1/samples/{sample_id}/annotations",
    ],
)
def test_recovery_and_shared_routes_remain_outside_optional_features(path):
    """Switches cannot prevent recovery or apply DNA-only policy to shared annotations."""
    routes = [route for entry in ROUTERS for route in entry.router.routes if route.path == path]
    assert routes
    assert all(not _required(route.dependant) for route in routes)


@pytest.mark.parametrize("keys", [(), ("unknown-feature",)])
def test_unknown_requirements_fail_when_the_router_is_built(keys):
    """Misspelled feature identities fail at startup rather than leaving a route unguarded."""
    with pytest.raises(ValueError):
        RequireModules(*keys)
