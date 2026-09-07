"""Tests for independent dashboard metric cache coordination."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from api.infra.dashboard_metric_cache import (
    DashboardMetricCache,
    invalidate_dashboard_metrics,
)


class _MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: object, timeout: int = 0):  # noqa: ARG002
        self.values[key] = value
        return True

    def add(self, key: str, value: object, timeout: int = 0):  # noqa: ARG002
        if key in self.values:
            return False
        self.values[key] = value
        return True

    def delete(self, key: str):
        return self.values.pop(key, None) is not None


def test_metric_cache_keeps_scopes_isolated() -> None:
    backend = _MemoryCache()
    cache = DashboardMetricCache(backend)

    cache.write("samples", {"total_samples": 3}, scope_key="role-a")
    cache.write("samples", {"total_samples": 7}, scope_key="role-b")

    assert cache.read("samples", scope_key="role-a").payload == {"total_samples": 3}
    assert cache.read("samples", scope_key="role-b").payload == {"total_samples": 7}


def test_metric_cache_marks_expired_and_invalidated_entries_stale() -> None:
    backend = _MemoryCache()
    cache = DashboardMetricCache(backend, fresh_seconds=60)
    cache.write("findings", {"total": 4})
    entry_key = cache._entry_key("findings", "global")
    backend.values[entry_key]["generated_at"] = datetime.now(timezone.utc) - timedelta(seconds=61)

    assert cache.read("findings").stale is True

    cache.write("findings", {"total": 5})
    cache.invalidate(["findings"])

    assert cache.read("findings").stale is True


def test_collection_invalidation_only_marks_dependent_metrics() -> None:
    backend = _MemoryCache()
    runtime = SimpleNamespace(
        cache=backend,
        config={
            "DASHBOARD_METRIC_CACHE_TTL_SECONDS": 300,
            "DASHBOARD_METRIC_CACHE_RETENTION_SECONDS": 3600,
        },
    )
    adapter = SimpleNamespace(app=runtime)
    cache = DashboardMetricCache(backend)
    cache.write("findings", {"total": 4})
    cache.write("panels", {"total": 2})

    invalidate_dashboard_metrics(adapter, collection="variants")

    assert cache.read("findings").stale is True
    assert cache.read("panels").stale is False


def test_configuration_invalidation_includes_resource_capacity() -> None:
    backend = _MemoryCache()
    runtime = SimpleNamespace(cache=backend, config={})
    adapter = SimpleNamespace(app=runtime)
    cache = DashboardMetricCache(backend)
    for metric in ("panels", "clinical_configuration", "resources", "findings"):
        cache.write(metric, {"metric": metric})

    invalidate_dashboard_metrics(adapter, collection="assay_specific_panels")

    assert cache.read("panels").stale is True
    assert cache.read("clinical_configuration").stale is True
    assert cache.read("resources").stale is True
    assert cache.read("findings").stale is False


def test_refresh_lock_allows_one_worker_until_released() -> None:
    cache = DashboardMetricCache(_MemoryCache())

    assert cache.acquire_refresh("samples", scope_key="role-a") is True
    assert cache.acquire_refresh("samples", scope_key="role-a") is False
    assert cache.acquire_refresh("samples", scope_key="role-b") is True

    cache.release_refresh("samples", scope_key="role-a")

    assert cache.acquire_refresh("samples", scope_key="role-a") is True
