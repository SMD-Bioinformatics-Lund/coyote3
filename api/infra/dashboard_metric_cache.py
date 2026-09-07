"""Cache coordination and invalidation for independently computed dashboard metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

DASHBOARD_METRICS = frozenset(
    {
        "samples",
        "findings",
        "top_tiered_genes",
        "panels",
        "clinical_configuration",
        "resources",
    }
)

COLLECTION_METRIC_DEPENDENCIES: dict[str, frozenset[str]] = {
    "samples": frozenset({"samples"}),
    "variants": frozenset({"findings"}),
    "cnvs": frozenset({"findings"}),
    "fusions": frozenset({"findings"}),
    "translocations": frozenset({"findings"}),
    "blacklist": frozenset({"findings"}),
    "reported_variants": frozenset({"findings"}),
    "annotation": frozenset({"findings", "top_tiered_genes"}),
    "reports": frozenset({"samples", "findings"}),
    "assay_specific_panels": frozenset({"panels", "clinical_configuration", "resources"}),
    "asp_configs": frozenset({"panels", "resources"}),
    "insilico_genelists": frozenset({"clinical_configuration", "resources"}),
    "users": frozenset({"samples", "resources"}),
    "roles": frozenset({"samples", "resources"}),
}


@dataclass(frozen=True)
class CachedDashboardMetric:
    payload: dict[str, Any]
    generated_at: datetime
    stale: bool


class DashboardMetricCache:
    """Read, write, and invalidate metric cache entries without Redis key scans."""

    def __init__(self, cache: Any, *, fresh_seconds: int = 300, retention_seconds: int = 3600):
        self.cache = cache
        self.fresh_seconds = max(int(fresh_seconds), 1)
        self.retention_seconds = max(int(retention_seconds), self.fresh_seconds)

    @staticmethod
    def _entry_key(metric: str, scope_key: str) -> str:
        return f"dashboard:metric:{metric}:{scope_key}"

    @staticmethod
    def _generation_key(metric: str) -> str:
        return f"dashboard:generation:{metric}"

    def read(self, metric: str, *, scope_key: str = "global") -> CachedDashboardMetric | None:
        entry = self.cache.get(self._entry_key(metric, scope_key))
        if not isinstance(entry, dict) or not isinstance(entry.get("payload"), dict):
            return None
        generated_at = entry.get("generated_at")
        if not isinstance(generated_at, datetime):
            return None
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        invalidated_at = self.cache.get(self._generation_key(metric))
        stale = (datetime.now(timezone.utc) - generated_at).total_seconds() > self.fresh_seconds
        if isinstance(invalidated_at, datetime):
            if invalidated_at.tzinfo is None:
                invalidated_at = invalidated_at.replace(tzinfo=timezone.utc)
            stale = stale or invalidated_at > generated_at
        return CachedDashboardMetric(dict(entry["payload"]), generated_at, stale)

    def write(self, metric: str, payload: dict[str, Any], *, scope_key: str = "global") -> datetime:
        generated_at = datetime.now(timezone.utc)
        self.cache.set(
            self._entry_key(metric, scope_key),
            {"payload": payload, "generated_at": generated_at},
            timeout=self.retention_seconds,
        )
        return generated_at

    def invalidate(self, metrics: Iterable[str]) -> None:
        invalidated_at = datetime.now(timezone.utc)
        for metric in set(metrics) & DASHBOARD_METRICS:
            self.cache.set(self._generation_key(metric), invalidated_at, timeout=0)

    def acquire_refresh(self, metric: str, *, scope_key: str = "global") -> bool:
        return self.cache.add(
            f"dashboard:refresh:{metric}:{scope_key}", True, timeout=max(self.fresh_seconds, 30)
        )

    def release_refresh(self, metric: str, *, scope_key: str = "global") -> None:
        self.cache.delete(f"dashboard:refresh:{metric}:{scope_key}")


def metric_cache_from_runtime(runtime: Any) -> DashboardMetricCache:
    config = getattr(runtime, "config", {}) or {}
    return DashboardMetricCache(
        getattr(runtime, "cache", None),
        fresh_seconds=int(config.get("DASHBOARD_METRIC_CACHE_TTL_SECONDS", 300) or 300),
        retention_seconds=int(config.get("DASHBOARD_METRIC_CACHE_RETENTION_SECONDS", 3600) or 3600),
    )


def invalidate_dashboard_metrics(adapter: Any, *, collection: str | None = None) -> None:
    """Invalidate only metrics that depend on the mutated collection."""
    metrics = COLLECTION_METRIC_DEPENDENCIES.get(str(collection or ""), DASHBOARD_METRICS)
    runtime = getattr(adapter, "app", None)
    cache = getattr(runtime, "cache", None)
    if cache is not None:
        metric_cache_from_runtime(runtime).invalidate(metrics)
