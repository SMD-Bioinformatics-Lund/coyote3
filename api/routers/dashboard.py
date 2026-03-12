"""Canonical dashboard router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.contracts.dashboard import DashboardSummaryPayload
from api.deps.services import get_dashboard_service
from api.extensions import util
from api.services.dashboard_service import DashboardService
from api.security.access import ApiUser, require_access

router = APIRouter(tags=["dashboard"])

if not hasattr(util, "common") or not hasattr(util, "dashboard"):
    util.init_util()


@router.get("/api/v1/dashboard/summary", response_model=DashboardSummaryPayload)
def dashboard_summary(
    user: ApiUser = Depends(require_access()),
    service: DashboardService = Depends(get_dashboard_service),
):
    return util.common.convert_to_serializable(service.summary_payload(user=user))


@router.get("/api/v1/dashboard/admin-insights")
def dashboard_admin_insights(
    user: ApiUser = Depends(require_access(min_role="admin", min_level=99999)),
    service: DashboardService = Depends(get_dashboard_service),
):
    _ = user
    return util.common.convert_to_serializable(service.build_admin_insights())
