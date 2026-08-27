"""Celery task-control helpers."""

from __future__ import annotations

from typing import Any

from api.app.deps.services import get_app_controls_service


def task_family_enabled(task_family: str) -> bool:
    """Return whether a task family is enabled in application controls."""
    try:
        return get_app_controls_service().task_enabled(task_family)
    except Exception:
        return True


def disabled_result(task_family: str) -> dict[str, Any]:
    """Return a standardized disabled-task result."""
    return {"status": "disabled", "task_family": task_family}
