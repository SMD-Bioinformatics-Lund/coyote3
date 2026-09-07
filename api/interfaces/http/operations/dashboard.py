"""Canonical dashboard router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.app.container import util
from api.app.deps.services import get_dashboard_service
from api.application.dashboard.analytics import DashboardService
from api.contracts.dashboard import (
    DashboardAdminInsightsPayload,
    DashboardMetricPayload,
    DashboardMetricRefreshRequest,
    DashboardRefreshQueuedPayload,
)
from api.infra.dashboard_metric_cache import DASHBOARD_METRICS
from api.interfaces.http.tags import TAG_DASHBOARD
from api.security.access import ApiUser, require_access
from api.tasks.maintenance import refresh_dashboard_metrics

router = APIRouter(tags=[TAG_DASHBOARD])


def _metric_response(metric: str, *, user: ApiUser, service: DashboardService):
    payload = service.metric_payload(metric, user=user)
    if payload.get("metric_meta", {}).get("stale") and service.acquire_metric_refresh(
        metric, user=user
    ):
        refresh_dashboard_metrics.delay(username=user.username, metrics=[metric])
    return util.common.convert_to_serializable(payload)


@router.get("/api/v1/dashboard/metrics/samples", response_model=DashboardMetricPayload)
def dashboard_sample_metrics(
    user: ApiUser = Depends(require_access()),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _metric_response("samples", user=user, service=service)


@router.get("/api/v1/dashboard/metrics/findings", response_model=DashboardMetricPayload)
def dashboard_finding_metrics(
    user: ApiUser = Depends(require_access()),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _metric_response("findings", user=user, service=service)


@router.get("/api/v1/dashboard/metrics/top-tiered-genes", response_model=DashboardMetricPayload)
def dashboard_top_tiered_gene_metrics(
    user: ApiUser = Depends(require_access()),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _metric_response("top_tiered_genes", user=user, service=service)


@router.get("/api/v1/dashboard/metrics/panels", response_model=DashboardMetricPayload)
def dashboard_panel_metrics(
    user: ApiUser = Depends(require_access()),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _metric_response("panels", user=user, service=service)


@router.get(
    "/api/v1/dashboard/metrics/clinical-configuration",
    response_model=DashboardMetricPayload,
)
def dashboard_clinical_configuration_metrics(
    user: ApiUser = Depends(require_access()),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _metric_response("clinical_configuration", user=user, service=service)


@router.get("/api/v1/dashboard/metrics/resources", response_model=DashboardMetricPayload)
def dashboard_resource_metrics(
    user: ApiUser = Depends(require_access()),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _metric_response("resources", user=user, service=service)


@router.post(
    "/api/v1/dashboard/metrics/refresh",
    response_model=DashboardRefreshQueuedPayload,
    status_code=status.HTTP_202_ACCEPTED,
)
def refresh_dashboard_metric_cache(
    request: DashboardMetricRefreshRequest,
    user: ApiUser = Depends(require_access()),
):
    """Queue an immediate refresh of selected metrics for the current user scope."""
    metrics = request.metrics or sorted(DASHBOARD_METRICS)
    unknown = sorted(set(metrics) - DASHBOARD_METRICS)
    if unknown:
        raise HTTPException(
            status_code=422, detail=f"Unknown dashboard metrics: {', '.join(unknown)}"
        )
    task = refresh_dashboard_metrics.delay(username=user.username, metrics=metrics)
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
