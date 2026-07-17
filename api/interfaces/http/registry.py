"""Central router registry for the FastAPI app."""

from __future__ import annotations

from api.interfaces.http.admin import router as admin_router
from api.interfaces.http.app_controls import router as app_controls_router
from api.interfaces.http.auth import http_exception_handler as auth_http_exception_handler
from api.interfaces.http.auth import router as auth_router
from api.interfaces.http.biomarkers import router as biomarkers_router
from api.interfaces.http.classifications import router as classifications_router
from api.interfaces.http.cnvs import router as cnvs_router
from api.interfaces.http.common import router as common_router
from api.interfaces.http.coverage import router as coverage_router
from api.interfaces.http.dashboard import router as dashboard_router
from api.interfaces.http.fusions import router as fusions_router
from api.interfaces.http.health import router as health_router
from api.interfaces.http.internal import router as internal_router
from api.interfaces.http.permissions import router as permissions_router
from api.interfaces.http.public import router as public_router
from api.interfaces.http.reports import router as reports_router
from api.interfaces.http.resources.asp import router as resource_asp_router
from api.interfaces.http.resources.aspc import router as resource_aspc_router
from api.interfaces.http.resources.genelists import router as resource_genelists_router
from api.interfaces.http.resources.samples import router as resource_samples_router
from api.interfaces.http.roles import router as roles_router
from api.interfaces.http.samples import router as samples_router
from api.interfaces.http.small_variants import router as small_variants_router
from api.interfaces.http.translocations import router as translocations_router
from api.interfaces.http.users import router as users_router

ROUTERS = (
    health_router,
    auth_router,
    admin_router,
    app_controls_router,
    resource_asp_router,
    resource_aspc_router,
    resource_genelists_router,
    resource_samples_router,
    biomarkers_router,
    classifications_router,
    common_router,
    cnvs_router,
    coverage_router,
    dashboard_router,
    fusions_router,
    internal_router,
    roles_router,
    permissions_router,
    public_router,
    reports_router,
    samples_router,
    small_variants_router,
    translocations_router,
    users_router,
)

__all__ = ["ROUTERS", "auth_http_exception_handler"]
