"""Canonical dashboard router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.app.container import util
from api.app.deps.services import get_dashboard_service
from api.application.dashboard.analytics import DashboardService
from api.contracts.dashboard import DashboardAdminInsightsPayload, DashboardSummaryPayload
from api.security.access import ApiUser, require_access

router = APIRouter(tags=["dashboard"])


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
    return util.common.convert_to_serializable(service.summary_payload(user=user))


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
