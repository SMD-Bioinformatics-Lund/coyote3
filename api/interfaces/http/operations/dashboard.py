"""Canonical dashboard router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.app.container import util
from api.app.deps.services import get_dashboard_service
from api.application.dashboard.analytics import DashboardService, DashboardSnapshotUnavailable
from api.contracts.dashboard import (
    DashboardAdminInsightsPayload,
    DashboardRefreshQueuedPayload,
    DashboardSummaryPayload,
)
from api.interfaces.http.tags import TAG_DASHBOARD
from api.security.access import ApiUser, require_access
from api.tasks.maintenance import refresh_dashboard_metrics

router = APIRouter(tags=[TAG_DASHBOARD])


@router.get("/api/v1/dashboard/summary", response_model=DashboardSummaryPayload)
def dashboard_summary(
    user: ApiUser = Depends(require_access()),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Return the dashboard summary for the current user.

    Args:
        user: Authenticated user requesting the summary.
        service: Dashboard workflow service.

    Returns:
        dict: Dashboard summary payload.
    """
    try:
        payload = service.summary_payload(user=user)
    except DashboardSnapshotUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return util.common.convert_to_serializable(payload)


@router.post(
    "/api/v1/dashboard/summary/refresh",
    response_model=DashboardRefreshQueuedPayload,
    status_code=status.HTTP_202_ACCEPTED,
)
def refresh_dashboard_summary(user: ApiUser = Depends(require_access())):
    """Queue an immediate dashboard metrics refresh for the current user scope."""
    task = refresh_dashboard_metrics.delay(username=user.username)
    return {"status": "queued", "task_id": str(task.id)}


@router.get("/api/v1/dashboard/admin-insights", response_model=DashboardAdminInsightsPayload)
def dashboard_admin_insights(
    user: ApiUser = Depends(require_access(permission="dashboard.admin:view")),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Return administrative dashboard insights.

    Args:
        user: Authenticated admin user.
        service: Dashboard workflow service.

    Returns:
        dict: Administrative dashboard insight payload.
    """
    _ = user
    return util.common.convert_to_serializable(service.build_admin_insights())
