"""Celery inspection and filesystem retention adapters for operational workflows."""

from __future__ import annotations

import gzip
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from coyote3.application.admin.app_controls import _task_summary, _worker_runtime_details


def inspect_celery_runtime(celery_app: Any, *, enabled: bool, timeout: float) -> dict[str, Any]:
    """Observe worker and beat state without exposing task arguments.

    Args:
        celery_app: Configured Celery application supplied by the composition root.
        enabled: Whether application controls permit task execution.
        timeout: Worker inspection timeout in seconds.

    Returns:
        Worker, queue and schedule observations for the operational status response.
    """
    inspect = celery_app.control.inspect(timeout=timeout)
    active = inspect.active() or {}
    reserved = inspect.reserved() or {}
    scheduled = inspect.scheduled() or {}
    stats = inspect.stats() or {}
    registered = inspect.registered() or {}
    active_queues = inspect.active_queues() or {}
    queue_names = {
        queue.get("name")
        for worker_queues in active_queues.values()
        for queue in worker_queues or []
        if isinstance(queue, dict)
    }
    queue_names.update(
        (
            delivery.get("routing_key")
            for worker_tasks in active.values()
            for task in worker_tasks
            if isinstance(task, dict)
            for delivery in [task.get("delivery_info") or {}]
            if delivery.get("routing_key")
        )
    )
    registered_tasks = sorted({task for tasks in registered.values() for task in tasks or []})
    queue_consumers: dict[str, list[str]] = {}
    for worker_name, worker_queues in active_queues.items():
        for queue in worker_queues or []:
            if not isinstance(queue, dict) or not queue.get("name"):
                continue
            queue_consumers.setdefault(str(queue["name"]), []).append(worker_name)
    beat_entries = [
        {"name": name, "task": entry.get("task"), "schedule": str(entry.get("schedule"))}
        for name, entry in sorted((celery_app.conf.beat_schedule or {}).items())
        if isinstance(entry, dict)
    ]
    workers_online = len(stats)
    if enabled:
        execution_state = "ready" if workers_online else "workers_missing"
    else:
        execution_state = (
            "execution_disabled_workers_online" if workers_online else "execution_disabled"
        )
    return {
        "status": "online" if stats else "offline",
        "execution_state": execution_state,
        "workers_online": workers_online,
        "worker_names": sorted(stats),
        "worker_details": _worker_runtime_details(
            stats, active, reserved, scheduled, registered, active_queues
        ),
        "active_count": sum((len(tasks or []) for tasks in active.values())),
        "reserved_count": sum((len(tasks or []) for tasks in reserved.values())),
        "scheduled_count": sum((len(tasks or []) for tasks in scheduled.values())),
        "registered_task_count": len(registered_tasks),
        "registered_tasks": registered_tasks,
        "beat_schedule_count": len(beat_entries),
        "beat_entries": beat_entries,
        "queue_names": sorted((name for name in queue_names if name)),
        "queue_consumers": {
            name: sorted(consumers) for name, consumers in sorted(queue_consumers.items())
        },
        "tasks": [
            *_task_summary(active, state="active"),
            *_task_summary(reserved, state="reserved"),
            *_task_summary(scheduled, state="scheduled"),
        ],
    }


def cleanup_disk_logs(
    *, log_root: str, retention_days: int, gzip_after_days: int
) -> dict[str, Any]:
    """Compress and erase logs using the application-selected retention intervals.

    Args:
        log_root: Configured log directory; user expansion is performed here.
        retention_days: Days to retain log files.
        gzip_after_days: Days before compressing plain-text logs.

    Returns:
        Compression/deletion counts and the directory status.
    """
    log_root = Path(log_root).expanduser()
    if not log_root.exists() or not log_root.is_dir():
        return {"log_root": str(log_root), "gzipped": 0, "deleted": 0, "status": "not_found"}
    now = datetime.now(timezone.utc)
    gzip_before = now - timedelta(days=gzip_after_days)
    delete_before = now - timedelta(days=retention_days)
    gzipped = 0
    deleted = 0
    for path in log_root.rglob("*.log*"):
        if not path.is_file():
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        if modified < delete_before:
            path.unlink(missing_ok=True)
            deleted += 1
            continue
        if path.suffix == ".gz" or modified >= gzip_before:
            continue
        gz_path = path.with_name(f"{path.name}.gz")
        if gz_path.exists():
            continue
        with path.open("rb") as src, gzip.open(gz_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        path.unlink(missing_ok=True)
        gzipped += 1
    return {"log_root": str(log_root), "gzipped": gzipped, "deleted": deleted, "status": "ok"}
