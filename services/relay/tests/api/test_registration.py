"""Optional Relay routes retain their host authentication and module boundaries."""

import inspect
from importlib.metadata import entry_points
from types import SimpleNamespace

import pytest
from coyote.config.governance_catalog import load_governance_catalog
from coyote_api.app import extensions
from coyote_api.app.deps.modules import RequireModules
from coyote_api.app.main import create_api_app
from coyote_api.app.openapi import MACHINE_INGEST_PATHS
from coyote_api.interfaces.http.tags import TAG_INGESTION, TAG_SYSTEM
from fastapi.routing import iter_route_contexts

from coyote_relay.api import routers


def _install(monkeypatch, enabled):
    """Select installed factory metadata independently of the development environment."""
    entries = (SimpleNamespace(name="relay", load=lambda: routers),) if enabled else ()
    monkeypatch.setattr(extensions, "entry_points", lambda **_: entries)
    return create_api_app()


def _dependencies(dependant):
    """Traverse nested FastAPI dependencies, including route and router declarations."""
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _dependencies(dependency)


def test_relay_advertises_its_installed_router_factory():
    entries = [entry for entry in entry_points(group="coyote.api.routers") if entry.name == "relay"]
    assert len(entries) == 1
    assert entries[0].load() is routers


def test_installation_exposes_all_ingestion_contracts_once(monkeypatch):
    app = _install(monkeypatch, True)
    schema = app.openapi()
    paths = {route.path for router in routers() for route in router.routes}
    assert app.state.api_extensions == ("relay",)
    assert paths <= schema["paths"].keys()
    assert "/api/v1/internal/metrics" not in schema["paths"]
    assert "/api/v1/internal/roles/levels" not in schema["paths"]
    assert "/api/v1/internal/isgl/{isgl_id}/meta" not in schema["paths"]
    assert schema["paths"]["/api/v1/health"]["get"]["tags"] == [TAG_SYSTEM]
    operations = [operation for path in paths for operation in schema["paths"][path].values()]
    assert all(operation["tags"] == [TAG_INGESTION] for operation in operations)
    operation_ids = [operation["operationId"] for operation in operations]
    assert len(operation_ids) == len(set(operation_ids))
    assert "InternalIngestSampleBundleRequest" in schema["components"]["schemas"]


def test_absent_relay_removes_runtime_routes_and_documentation_without_state_leaks(monkeypatch):
    with_relay = _install(monkeypatch, True)
    assert "/api/v1/internal/ingest/sample-bundle" in with_relay.openapi()["paths"]
    standalone = _install(monkeypatch, False)
    paths = {route.path for router in routers() for route in router.routes}
    runtime_paths = {getattr(route, "path", "") for route in iter_route_contexts(standalone.routes)}
    schema = standalone.openapi()
    assert standalone.state.api_extensions == ()
    assert not paths & runtime_paths
    assert not paths & schema["paths"].keys()
    assert TAG_INGESTION not in {tag["name"] for tag in schema["tags"]}
    assert all(TAG_INGESTION not in group["tags"] for group in schema["x-tagGroups"])
    assert "InternalIngestSampleBundleRequest" not in schema["components"]["schemas"]


def test_ingestion_authentication_contract_survives_optional_installation(monkeypatch):
    schema = _install(monkeypatch, True).openapi()
    for router in routers():
        for route in router.routes:
            for method in route.methods:
                security = schema["paths"][route.path][method.lower()]["security"]
                assert {"ApiSessionCookie": []} in security
                assert {"BearerAuth": []} in security
                assert ({"IngestToken": []} in security) is (route.path in MACHINE_INGEST_PATHS)
                assert ({"InternalToken": []} in security) is (route.path in MACHINE_INGEST_PATHS)


@pytest.mark.parametrize("route", [route for router in routers() for route in router.routes])
def test_relay_routes_keep_authentication_and_module_gates(route):
    calls = list(_dependencies(route.dependant))
    names = {getattr(call, "__name__", "") for call in calls}
    assert names & {
        "dep",
        "require_sample_ingest_access",
        "require_sample_ingest_user_access",
        "require_ingest_job_access",
    }, route.path
    modules = {
        key for call in calls if isinstance(call, RequireModules) for key in call.module_keys
    }
    expected = set() if route.path == "/api/v1/internal/tasks/{task_id}" else {"ingest_workspace"}
    assert modules == expected
    catalog = {str(item["permission_id"]) for item in load_governance_catalog("permissions")}
    for call in calls:
        if getattr(call, "__name__", "") == "dep":
            permission = inspect.getclosurevars(call).nonlocals.get("permission")
            assert permission is None or permission in catalog
