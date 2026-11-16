"""Installed API extensions fail closed on broken or ambiguous registrations."""

from types import SimpleNamespace

import pytest
from coyote_api.app import extensions
from fastapi import APIRouter


def _router(path="/api/v1/example", methods=None):
    """Create a synthetic extension router without any persistence dependency."""
    router = APIRouter()
    router.add_api_route(path, lambda: {}, methods=methods or ["GET"])
    return router


def _entry(name, *routers):
    """Represent installed package metadata with a deterministic router factory."""
    return SimpleNamespace(name=name, load=lambda: lambda: routers)


def _installed(monkeypatch, *entries):
    """Keep extension discovery independent of packages in the test environment."""

    def discover(*, group):
        assert group == "coyote.api.routers"
        return entries

    monkeypatch.setattr(extensions, "entry_points", discover)


def test_no_extensions_keeps_server_standalone(monkeypatch):
    _installed(monkeypatch)
    assert extensions.load_api_extensions([]) == extensions.ApiExtensions((), ())


def test_explicitly_disabled_extension_exposes_no_capability(monkeypatch):
    _installed(monkeypatch, SimpleNamespace(name="demo", load=lambda: lambda: None))
    assert extensions.load_api_extensions([]) == extensions.ApiExtensions((), ())


def test_disabled_extension_cannot_hide_duplicate_registration(monkeypatch):
    _installed(
        monkeypatch,
        SimpleNamespace(name="demo", load=lambda: lambda: None),
        _entry("demo", _router()),
    )
    with pytest.raises(RuntimeError, match="Duplicate API extension name"):
        extensions.load_api_extensions([])


def test_extensions_register_in_deterministic_order(monkeypatch):
    first, second = _router("/api/v1/first"), _router("/api/v1/second")
    _installed(monkeypatch, _entry("second", second), _entry("first", first))
    assert extensions.load_api_extensions([]) == extensions.ApiExtensions(
        ("first", "second"), (first, second)
    )


def test_broken_installed_package_prevents_startup(monkeypatch):
    failure = ImportError("missing dependency")

    def load():
        raise failure

    _installed(monkeypatch, SimpleNamespace(name="broken", load=load))
    with pytest.raises(RuntimeError, match="Cannot load installed API extension: broken") as caught:
        extensions.load_api_extensions([])
    assert caught.value.__cause__ is failure


@pytest.mark.parametrize("routers", [(), (object(),)])
def test_invalid_factory_result_prevents_startup(monkeypatch, routers):
    _installed(monkeypatch, _entry("invalid", *routers))
    with pytest.raises(RuntimeError, match="must provide APIRouter"):
        extensions.load_api_extensions([])


def test_duplicate_extension_names_prevent_startup(monkeypatch):
    _installed(monkeypatch, _entry("same", _router()), _entry("same", _router("/api/v1/other")))
    with pytest.raises(RuntimeError, match="Duplicate API extension name"):
        extensions.load_api_extensions([])


@pytest.mark.parametrize("path", ["/public/example", "/api/v2/example", "/api/v1"])
def test_extensions_cannot_escape_versioned_host_middleware(monkeypatch, path):
    _installed(monkeypatch, _entry("invalid", _router(path)))
    with pytest.raises(RuntimeError, match="non-versioned route"):
        extensions.load_api_extensions([])


def test_non_http_route_prevents_startup(monkeypatch):
    router = APIRouter()
    router.add_websocket_route("/api/v1/socket", lambda: None)
    _installed(monkeypatch, _entry("invalid", router))
    with pytest.raises(RuntimeError, match="non-versioned route"):
        extensions.load_api_extensions([])


@pytest.mark.parametrize("path", ["/api/v1/items/{id}", "/api/v1/items/{name}"])
def test_extension_cannot_shadow_builtin_operation(monkeypatch, path):
    _installed(monkeypatch, _entry("conflicting", _router(path)))
    with pytest.raises(RuntimeError, match="conflicts with an existing HTTP operation"):
        extensions.load_api_extensions([_router("/api/v1/items/{id}")])


def test_distinct_methods_can_share_path(monkeypatch):
    plugin = _router(methods=["POST"])
    _installed(monkeypatch, _entry("valid", plugin))
    assert extensions.load_api_extensions([_router()]).routers == (plugin,)


def test_duplicate_routes_inside_one_router_prevent_startup(monkeypatch):
    router = _router()
    router.add_api_route("/api/v1/example", lambda: {})
    _installed(monkeypatch, _entry("conflicting", router))
    with pytest.raises(RuntimeError, match="conflicts with an existing HTTP operation"):
        extensions.load_api_extensions([])


def test_duplicate_routes_across_extensions_prevent_startup(monkeypatch):
    _installed(monkeypatch, _entry("first", _router()), _entry("second", _router()))
    with pytest.raises(RuntimeError, match="conflicts with an existing HTTP operation"):
        extensions.load_api_extensions([])
