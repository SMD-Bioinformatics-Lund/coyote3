"""Canonical dashboard router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.contracts.dashboard import DashboardSummaryPayload
from api.deps.services import get_dashboard_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.dashboard.analytics import DashboardService

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


@router.get("/api/v1/dashboard/admin-insights")
def dashboard_admin_insights(
    user: ApiUser = Depends(require_access(min_role="admin", min_level=99999)),
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
