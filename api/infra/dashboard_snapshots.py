"""Dashboard materialized-view invalidation."""

from __future__ import annotations

from datetime import datetime, timezone


def mark_dashboard_summaries_dirty(adapter) -> None:
    """Mark persisted dashboard summaries stale after source data changes."""
    app_obj = getattr(adapter, "app", None)
    logger = getattr(app_obj, "logger", None)
    try:
        adapter.coyote_db["dashboard_metrics"].update_many(
            {"_id": {"$regex": r"^dashboard_summary:"}},
            {"$set": {"dirty_since": datetime.now(timezone.utc)}},
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        if logger is not None:
            logger.warning("dashboard_summary_invalidation_failed error=%s", exc)
