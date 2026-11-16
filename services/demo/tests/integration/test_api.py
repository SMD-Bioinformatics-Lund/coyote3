"""Optional demo routes require explicit isolation and retain session authorization."""

import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote_api.config.runtime_settings import DefaultConfig
from coyote_demo import api
from coyote_demo.api import dependencies, routes
from coyote_demo.deployment import runtime_validator
from demo_test_support.deployment import demo_settings


def _configure(monkeypatch):
    """Supply only synthetic settings without connecting to any database endpoint."""
    settings = demo_settings()
    for key in runtime_validator.configuration_keys:
        monkeypatch.setattr(DefaultConfig, key, settings.get(key), raising=False)
    monkeypatch.setenv("COYOTE_DEMO_ENABLED", "1")
    return settings


def test_enabled_factory_keeps_original_private_paths_and_permissions(monkeypatch):
    _configure(monkeypatch)
    registered = api.routers()
    assert registered == (routes.router,)
    assert {route.path for route in routes.router.routes} == {
        "/api/v1/admin/demo-installation",
        "/api/v1/admin/demo-installation/starter",
        "/api/v1/admin/demo-installation/configuration",
        "/api/v1/admin/demo-installation/samples/{key}",
    }
    for route in routes.router.routes:
        assert not route.include_in_schema
        checks = [dependency.call for dependency in route.dependant.dependencies]
        permission = [
            inspect.getclosurevars(call).nonlocals.get("permission")
            for call in checks
            if getattr(call, "__name__", "") == "dep"
        ]
        assert permission == ["demo:install"]


def test_enabled_factory_rejects_ordinary_target(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(DefaultConfig, "COYOTE4_DB", "coyote4_prod")
    with pytest.raises(ValueError, match="COYOTE4_DB"):
        api.routers()


@pytest.mark.parametrize(
    "handler,method,args",
    [
        (routes.demo_installation_plan, "plan", ()),
        (routes.install_demo_starter, "starter", ()),
        (routes.install_demo_configuration, "configuration", ()),
        (routes.install_demo_sample, "sample", ("first_sample",)),
    ],
)
def test_routes_delegate_to_authorized_package_operations(handler, method, args):
    service = Mock()
    getattr(service, method).return_value = {"status": "synthetic"}
    assert handler(*args, user=object(), service=service) == {"status": "synthetic"}
    getattr(service, method).assert_called_once_with(*args)


def test_host_dependency_rejects_unsafe_settings_before_store_resolution(monkeypatch):
    monkeypatch.setattr(
        dependencies.runtime_app, "config", demo_settings() | {"COYOTE4_DB": "ordinary"}
    )
    store = Mock()
    monkeypatch.setattr(dependencies, "get_store", store)
    with pytest.raises(ValueError, match="COYOTE4_DB"):
        dependencies.get_demo_service()
    store.assert_not_called()


def test_current_session_is_bound_before_resolving_demo_services(monkeypatch):
    session = SimpleNamespace(token="synthetic-session")
    runtime = object()
    monkeypatch.setattr(dependencies, "get_request_api_session", lambda request: session)
    bind = Mock(return_value=runtime)
    monkeypatch.setattr(dependencies, "open_authenticated_runtime", bind)
    operation = dependencies.get_demo_installation(object())
    bind.assert_called_once()
    assert bind.call_args.args == (session.token,)
    assert operation._runtime is runtime
