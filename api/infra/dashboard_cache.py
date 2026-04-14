"""Shared helpers for dashboard summary cache/snapshot invalidation."""

from __future__ import annotations

import uuid


def invalidate_dashboard_summary_cache(adapter) -> None:
    """Invalidate dashboard summary snapshots and bump cache version token."""
    app_obj = getattr(adapter, "app", None)
    logger = getattr(app_obj, "logger", None)

    try:
        adapter.coyote_db["dashboard_metrics"].delete_many(
            {"_id": {"$regex": r"^dashboard_summary_v2:"}}
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        if logger is not None:
            logger.warning("dashboard_summary_snapshot_invalidate_failed error=%s", exc)

    cache = getattr(app_obj, "cache", None)
    if cache is None:
        return
    try:
        cache.set(
            "dashboard:summary:version",
            uuid.uuid4().hex,
            timeout=60 * 60 * 24 * 30,
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        if logger is not None:
            logger.warning("dashboard_summary_cache_version_bump_failed error=%s", exc)
