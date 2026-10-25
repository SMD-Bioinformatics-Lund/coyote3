"""Central router registry for the FastAPI app."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter

from api.interfaces.http.v1.admin.clinical_rules import router as clinical_rules_router
from api.interfaces.http.v1.admin.configuration_profiles import (
    router as configuration_profiles_router,
)
from api.interfaces.http.v1.admin.deployment_data import router as deployment_data_router
from api.interfaces.http.v1.admin.operations import router as admin_operations_router
from api.interfaces.http.v1.admin.permissions import router as permissions_router
from api.interfaces.http.v1.admin.public_assay_catalog import router as public_assay_catalog_router
from api.interfaces.http.v1.admin.query_rules import router as query_rules_router
from api.interfaces.http.v1.admin.resources.asp import router as resource_asp_router
from api.interfaces.http.v1.admin.resources.aspc import router as resource_aspc_router
from api.interfaces.http.v1.admin.resources.assay_setup import router as assay_setup_router
from api.interfaces.http.v1.admin.resources.genelists import router as resource_genelists_router
from api.interfaces.http.v1.admin.resources.samples import router as resource_samples_router
from api.interfaces.http.v1.admin.roles import router as roles_router
from api.interfaces.http.v1.admin.users import router as users_router
from api.interfaces.http.v1.clinical.dna.biomarkers import router as biomarkers_router
from api.interfaces.http.v1.clinical.dna.classifications import router as classifications_router
from api.interfaces.http.v1.clinical.dna.cnvs import router as cnvs_router
from api.interfaces.http.v1.clinical.dna.coverage import router as coverage_router
from api.interfaces.http.v1.clinical.dna.small_variants import router as small_variants_router
from api.interfaces.http.v1.clinical.dna.translocations import router as translocations_router
from api.interfaces.http.v1.clinical.reporting.reports import router as reports_router
from api.interfaces.http.v1.clinical.rna.fusions import router as fusions_router
from api.interfaces.http.v1.clinical.samples import router as samples_router
from api.interfaces.http.v1.knowledgebase.common import router as common_router
from api.interfaces.http.v1.operations.app_controls import router as app_controls_router
from api.interfaces.http.v1.operations.auth import (
    http_exception_handler as auth_http_exception_handler,
)
from api.interfaces.http.v1.operations.auth import router as auth_router
from api.interfaces.http.v1.operations.client_errors import router as client_errors_router
from api.interfaces.http.v1.operations.dashboard import router as dashboard_router
from api.interfaces.http.v1.operations.editing import router as editing_router
from api.interfaces.http.v1.operations.health import router as health_router
from api.interfaces.http.v1.operations.internal import router as internal_router
from api.interfaces.http.v1.operations.notifications import router as notifications_router
from api.interfaces.http.v1.public.routes import router as public_router


@dataclass(frozen=True, slots=True)
class RouterRegistration:
    """Describe one router and whether it belongs to the supported API contract."""

    router: APIRouter
    include_in_schema: bool = True


ROUTERS = (
    RouterRegistration(editing_router),
    RouterRegistration(health_router, include_in_schema=False),
    RouterRegistration(client_errors_router, include_in_schema=False),
    RouterRegistration(auth_router),
    RouterRegistration(admin_operations_router),
    RouterRegistration(deployment_data_router),
    RouterRegistration(app_controls_router),
    RouterRegistration(resource_asp_router),
    RouterRegistration(assay_setup_router),
    RouterRegistration(resource_aspc_router),
    RouterRegistration(configuration_profiles_router),
    RouterRegistration(resource_genelists_router),
    RouterRegistration(resource_samples_router),
    RouterRegistration(biomarkers_router),
    RouterRegistration(classifications_router),
    RouterRegistration(common_router),
    RouterRegistration(cnvs_router),
    RouterRegistration(coverage_router),
    RouterRegistration(dashboard_router),
    RouterRegistration(fusions_router),
    RouterRegistration(internal_router, include_in_schema=False),
    RouterRegistration(notifications_router),
    RouterRegistration(roles_router),
    RouterRegistration(permissions_router),
    RouterRegistration(public_assay_catalog_router),
    RouterRegistration(public_router),
    RouterRegistration(reports_router),
    RouterRegistration(clinical_rules_router),
    RouterRegistration(query_rules_router),
    RouterRegistration(samples_router),
    RouterRegistration(small_variants_router),
    RouterRegistration(translocations_router),
    RouterRegistration(users_router),
)

__all__ = ["ROUTERS", "RouterRegistration", "auth_http_exception_handler"]
