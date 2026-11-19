"""Owned connections are closed without invalidating unrelated runtimes."""

import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote_api.app import lifecycle, runtime_setup
from coyote_api.app.container import MongoStore
from coyote_api.app.deps import services
from coyote_api.infra.cache import RedisCacheBackend, create_cache_backend
from coyote_mongo import runtime_adapter


def test_store_replacement_closes_old_adapter_and_removes_stale_handles(monkeypatch):
    first = SimpleNamespace(close=Mock(), initialize=Mock(), ping=Mock(), stale_collection=object())
    second = SimpleNamespace(
        close=Mock(), initialize=Mock(), ping=Mock(), sample_repository=object()
    )
    monkeypatch.setattr(runtime_adapter, "MongoAdapter", Mock(side_effect=[first, second]))
    store = MongoStore()
    store.init_from_app(Mock())
    store.init_from_app(Mock())
    first.close.assert_called_once()
    assert not hasattr(store, "stale_collection")
    assert store.sample_repository is second.sample_repository
    store.reset()
    store.reset()
    second.close.assert_called_once()
    with pytest.raises(RuntimeError, match="before API runtime initialization"):
        store.sample_repository.get_sample("synthetic")


def test_failed_ping_closes_new_adapter_and_preserves_previous_binding(monkeypatch):
    first = SimpleNamespace(close=Mock(), initialize=Mock(), ping=Mock(), client=object())
    second = SimpleNamespace(
        close=Mock(), initialize=Mock(), ping=Mock(side_effect=ValueError("ping"))
    )
    monkeypatch.setattr(runtime_adapter, "MongoAdapter", Mock(side_effect=[first, second]))
    store = MongoStore()
    store.init_from_app(Mock())
    with pytest.raises(ValueError, match="ping"):
        store.init_from_app(Mock())
    assert store.client is first.client
    first.close.assert_not_called()
    second.close.assert_called_once()
    store.reset()


def test_context_close_does_not_close_replacement_adapter():
    store = MongoStore()
    previous, current = Mock(), Mock()
    store._adapter = current
    cache = Mock()
    runtime = runtime_setup.ApiRuntimeContext({}, logging.getLogger("test"), cache, store)
    runtime._adapter = previous
    runtime.close()
    runtime.close()
    current.close.assert_not_called()
    cache.close.assert_called_once()


def test_partial_startup_releases_cache_on_database_failure(monkeypatch):
    cache = Mock()
    monkeypatch.setattr(runtime_setup, "_select_config", lambda **_: object())
    monkeypatch.setattr(runtime_setup, "_config_dict", lambda _: {})
    monkeypatch.setattr(runtime_setup.ApiRuntimeContext, "backend_settings", None)
    monkeypatch.setattr(runtime_setup, "configure_json_logging", Mock())
    monkeypatch.setattr(
        runtime_setup, "_init_cache", lambda runtime: setattr(runtime, "cache", cache)
    )
    monkeypatch.setattr(runtime_setup, "_init_store", Mock(side_effect=RuntimeError("database")))
    with pytest.raises(RuntimeError, match="database"):
        runtime_setup.create_runtime_context(testing=True)
    cache.close.assert_called_once()


def test_shutdown_invalidates_cached_services(monkeypatch):
    factory = Mock(side_effect=[object(), object()])
    cached = services._runtime_cached(factory)
    first = cached()
    assert cached() is first
    runtime = Mock()
    monkeypatch.setattr(lifecycle, "_runtime_context", runtime)
    monkeypatch.setattr(lifecycle, "_runtime_initialized", True)
    monkeypatch.setattr(lifecycle, "_lifespan_owners", 0)
    monkeypatch.setattr(lifecycle, "_runtime_mode", (True, False))
    monkeypatch.setattr(lifecycle, "_process_owner", True)
    lifecycle.shutdown_runtime()
    assert cached() is not first
    runtime.close.assert_called_once()


def test_failed_redis_ping_closes_client(monkeypatch):
    client = Mock()
    client.ping.side_effect = ConnectionError("unavailable")
    monkeypatch.setattr("coyote_api.infra.cache.redis.Redis.from_url", Mock(return_value=client))
    with pytest.raises(RuntimeError, match="connection_failed"):
        create_cache_backend(
            config={"CACHE_REDIS_URL": "redis://synthetic.invalid", "CACHE_REQUIRED": True},
            logger=logging.getLogger("test"),
            namespace="test",
        )
    client.close.assert_called_once()


def test_redis_cache_shutdown_closes_owned_client():
    client = Mock()
    cache = RedisCacheBackend(client=client, key_prefix="test", default_timeout=30, logger=Mock())
    cache.close()
    client.close.assert_called_once()
