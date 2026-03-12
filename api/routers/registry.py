"""Central router registry for the FastAPI app."""

from __future__ import annotations

from api.routers.auth import http_exception_handler as auth_http_exception_handler
from api.routers.auth import router as auth_router
from api.routers.admin_resources import router as admin_resources_router
from api.routers.common import router as common_router
from api.routers.coverage import router as coverage_router
from api.routers.dashboard import router as dashboard_router
from api.routers.dna_structural import router as dna_structural_router
from api.routers.health import router as health_router
from api.routers.home import router as home_router
from api.routers.internal import router as internal_router
from api.routers.permissions import router as permissions_router
from api.routers.public import router as public_router
from api.routers.rna import router as rna_router
from api.routers.reports import router as reports_router
from api.routers.roles import router as roles_router
from api.routers.samples import router as samples_router
from api.routers.users import router as users_router
from api.routers.variants import router as variants_router

ROUTERS = (
    health_router,
    auth_router,
    admin_resources_router,
    common_router,
    coverage_router,
    dashboard_router,
    dna_structural_router,
    internal_router,
    home_router,
    roles_router,
    permissions_router,
    public_router,
    rna_router,
    reports_router,
    samples_router,
    users_router,
    variants_router,
)

__all__ = ["ROUTERS", "auth_http_exception_handler"]
