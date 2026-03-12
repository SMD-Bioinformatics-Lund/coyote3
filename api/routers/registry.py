"""Central router registry for the FastAPI app."""

from __future__ import annotations

from api.routers.auth import http_exception_handler as auth_http_exception_handler
from api.routers.auth import router as auth_router
from api.routers.biomarkers import router as biomarkers_router
from api.routers.classifications import router as classifications_router
from api.routers.cnvs import router as cnvs_router
from api.routers.common import router as common_router
from api.routers.coverage import router as coverage_router
from api.routers.dashboard import router as dashboard_router
from api.routers.fusions import router as fusions_router
from api.routers.health import router as health_router
from api.routers.internal import router as internal_router
from api.routers.permissions import router as permissions_router
from api.routers.public import router as public_router
from api.routers.reports import router as reports_router
from api.routers.resources.asp import router as resource_asp_router
from api.routers.resources.aspc import router as resource_aspc_router
from api.routers.resources.genelists import router as resource_genelists_router
from api.routers.resources.samples import router as resource_samples_router
from api.routers.resources.schemas import router as resource_schemas_router
from api.routers.roles import router as roles_router
from api.routers.samples import router as samples_router
from api.routers.small_variants import router as small_variants_router
from api.routers.translocations import router as translocations_router
from api.routers.users import router as users_router

ROUTERS = (
    health_router,
    auth_router,
    resource_asp_router,
    resource_aspc_router,
    resource_genelists_router,
    resource_samples_router,
    resource_schemas_router,
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
