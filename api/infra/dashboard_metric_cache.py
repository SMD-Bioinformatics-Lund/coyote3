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
    """Carry a metric payload, its generation time, and computed staleness."""

    payload: dict[str, Any]
    generated_at: datetime
    stale: bool


class DashboardMetricCache:
    """Read, write, and invalidate metric cache entries without Redis key scans."""

    def __init__(self, cache: Any, *, fresh_seconds: int = 300, retention_seconds: int = 3600):
        """Configure metric freshness and cache retention.

        Args:
            cache: Backend providing get, set, add, and delete operations.
            fresh_seconds: Freshness threshold in seconds, clamped to at least one.
            retention_seconds: Entry lifetime in seconds, clamped to at least the
                freshness threshold.
        """
        self.cache = cache
        self.fresh_seconds = max(int(fresh_seconds), 1)
        self.retention_seconds = max(int(retention_seconds), self.fresh_seconds)

    @staticmethod
    def _entry_key(metric: str, scope_key: str) -> str:
        """Build the cache key for one metric and visibility scope.

        Args:
            metric: Metric name.
            scope_key: Scope identifier distinguishing cached payloads.

        Returns:
            Dashboard metric entry key.
        """
        return f"dashboard:metric:{metric}:{scope_key}"

    @staticmethod
    def _generation_key(metric: str) -> str:
        """Build the invalidation timestamp key shared by a metric's scopes.

        Args:
            metric: Metric name.

        Returns:
            Dashboard generation key.
        """
        return f"dashboard:generation:{metric}"

    def read(self, metric: str, *, scope_key: str = "global") -> CachedDashboardMetric | None:
        """Read a retained metric and evaluate its age and invalidation timestamp.

        Args:
            metric: Metric name.
            scope_key: Payload scope, defaulting to the global scope.

        Returns:
            Cached payload and staleness, or ``None`` for a missing or malformed
            entry. Naive timestamps are interpreted as UTC.
        """
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
        """Attempt to cache a metric with the current UTC generation timestamp.

        Args:
            metric: Metric name.
            payload: Computed metric data.
            scope_key: Payload scope, defaulting to the global scope.

        Returns:
            Generation timestamp, even if the backend reports a failed write.
        """
        generated_at = datetime.now(timezone.utc)
        self.cache.set(
            self._entry_key(metric, scope_key),
            {"payload": payload, "generated_at": generated_at},
            timeout=self.retention_seconds,
        )
        return generated_at

    def invalidate(self, metrics: Iterable[str]) -> None:
        """Mark known metrics stale across all scopes without deleting payloads.

        Args:
            metrics: Metric names; duplicates and unknown names are ignored.

        Notes:
            Writes nonexpiring invalidation timestamps through the cache backend.
        """
        invalidated_at = datetime.now(timezone.utc)
        for metric in set(metrics) & DASHBOARD_METRICS:
            self.cache.set(self._generation_key(metric), invalidated_at, timeout=0)

    def acquire_refresh(self, metric: str, *, scope_key: str = "global") -> bool:
        """Attempt to reserve a metric refresh using a conditional cache entry.

        Args:
            metric: Metric name.
            scope_key: Payload scope, defaulting to the global scope.

        Returns:
            Whether the backend added the reservation. Its lifetime is the greater
            of the freshness threshold and 30 seconds.
        """
        return self.cache.add(
            f"dashboard:refresh:{metric}:{scope_key}", True, timeout=max(self.fresh_seconds, 30)
        )

    def release_refresh(self, metric: str, *, scope_key: str = "global") -> None:
        """Delete a metric refresh reservation.

        Args:
            metric: Metric name.
            scope_key: Payload scope, defaulting to the global scope.
        """
        self.cache.delete(f"dashboard:refresh:{metric}:{scope_key}")


def metric_cache_from_runtime(runtime: Any) -> DashboardMetricCache:
    """Construct a metric cache using runtime configuration and its backend.

    Args:
        runtime: Object exposing optional ``config`` and ``cache`` attributes.

    Returns:
        Cache wrapper using 300-second freshness and 3600-second retention when
        the respective settings are absent or falsey. A missing backend remains
        ``None``; this function does not validate its availability.
    """
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
