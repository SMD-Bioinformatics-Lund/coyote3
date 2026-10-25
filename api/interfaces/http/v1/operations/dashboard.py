"""Canonical dashboard router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from api.app.deps.application import get_dashboard
from api.interfaces.http.tags import TAG_DASHBOARD
from api.security.access import ApiUser, require_access
from coyote3.application.operations.system import Dashboard
from coyote3.contracts.dashboard import (
    DashboardAdminInsightsPayload,
    DashboardMetricPayload,
    DashboardMetricRefreshRequest,
    DashboardRefreshQueuedPayload,
)

router = APIRouter(tags=[TAG_DASHBOARD])


@router.get("/api/v1/dashboard/metrics/samples", response_model=DashboardMetricPayload)
def dashboard_sample_metrics(
    user: ApiUser = Depends(require_access()),
    service: Dashboard = Depends(get_dashboard),
):
    """Read sample metrics for the authenticated user's scope.

    \u000c

    Args:
        user: Authenticated user whose access scope selects the metrics.
        service: Dashboard service supplying cached sample metrics.

    Returns:
        Serialized sample metrics and cache metadata.

    Notes:
        A stale payload queues a background refresh if its refresh lock is acquired.
    """
    return service.metric("samples")


@router.get("/api/v1/dashboard/metrics/findings", response_model=DashboardMetricPayload)
def dashboard_finding_metrics(
    user: ApiUser = Depends(require_access()),
    service: Dashboard = Depends(get_dashboard),
):
    """Read finding metrics for the authenticated user's scope.

    \u000c

    Args:
        user: Authenticated user whose access scope selects the metrics.
        service: Dashboard service supplying cached finding metrics.

    Returns:
        Serialized finding metrics and cache metadata.

    Notes:
        A stale payload queues a background refresh if its refresh lock is acquired.
    """
    return service.metric("findings")


@router.get("/api/v1/dashboard/metrics/top-tiered-genes", response_model=DashboardMetricPayload)
def dashboard_top_tiered_gene_metrics(
    user: ApiUser = Depends(require_access()),
    service: Dashboard = Depends(get_dashboard),
):
    """Read top-tiered-gene metrics for the authenticated user's scope.

    \u000c

    Args:
        user: Authenticated user whose access scope selects the metrics.
        service: Dashboard service supplying cached top-tiered-gene metrics.

    Returns:
        Serialized top-tiered-gene metrics and cache metadata.

    Notes:
        A stale payload queues a background refresh if its refresh lock is acquired.
    """
    return service.metric("top_tiered_genes")


@router.get("/api/v1/dashboard/metrics/panels", response_model=DashboardMetricPayload)
def dashboard_panel_metrics(
    user: ApiUser = Depends(require_access()),
    service: Dashboard = Depends(get_dashboard),
):
    """Read panel metrics for the authenticated user's scope.

    \u000c

    Args:
        user: Authenticated user whose access scope selects the metrics.
        service: Dashboard service supplying cached panel metrics.

    Returns:
        Serialized panel metrics and cache metadata.

    Notes:
        A stale payload queues a background refresh if its refresh lock is acquired.
    """
    return service.metric("panels")


@router.get(
    "/api/v1/dashboard/metrics/clinical-configuration",
    response_model=DashboardMetricPayload,
)
def dashboard_clinical_configuration_metrics(
    user: ApiUser = Depends(require_access()),
    service: Dashboard = Depends(get_dashboard),
):
    """Read clinical-configuration metrics for the authenticated user's scope.

    \u000c

    Args:
        user: Authenticated user whose access scope selects the metrics.
        service: Dashboard service supplying cached clinical-configuration metrics.

    Returns:
        Serialized clinical-configuration metrics and cache metadata.

    Notes:
        A stale payload queues a background refresh if its refresh lock is acquired.
    """
    return service.metric("clinical_configuration")


@router.get("/api/v1/dashboard/metrics/resources", response_model=DashboardMetricPayload)
def dashboard_resource_metrics(
    user: ApiUser = Depends(require_access()),
    service: Dashboard = Depends(get_dashboard),
):
    """Read resource metrics for the authenticated user's scope.

    \u000c

    Args:
        user: Authenticated user whose access scope selects the metrics.
        service: Dashboard service supplying cached resource metrics.

    Returns:
        Serialized resource metrics and cache metadata.

    Notes:
        A stale payload queues a background refresh if its refresh lock is acquired.
    """
    return service.metric("resources")


@router.post(
    "/api/v1/dashboard/metrics/refresh",
    response_model=DashboardRefreshQueuedPayload,
    status_code=status.HTTP_202_ACCEPTED,
)
def refresh_dashboard_metric_cache(
    request: DashboardMetricRefreshRequest,
    user: ApiUser = Depends(require_access()),
    service: Dashboard = Depends(get_dashboard),
):
    """Queue an immediate refresh of selected metrics for the current user scope."""
    return service.refresh(request.metrics)


@router.get("/api/v1/dashboard/admin-insights", response_model=DashboardAdminInsightsPayload)
def dashboard_admin_insights(
    user: ApiUser = Depends(require_access(permission="dashboard.admin:view")),
    service: Dashboard = Depends(get_dashboard),
):
    """Return administrative dashboard insights.

    \u000c

    Args:
        user: Authenticated admin user.
        service: Dashboard workflow service.

    Returns:
        dict: Administrative dashboard insight payload.
    """
    return service.admin_insights()
