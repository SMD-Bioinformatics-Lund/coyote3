"""Service dependency factories."""

from functools import lru_cache

from api.deps.repositories import (
    get_admin_repository,
    get_coverage_processing_repository,
    get_coverage_repository,
    get_dashboard_repository,
    get_dna_repository,
    get_home_repository,
    get_rna_repository,
    get_rna_workflow_repository,
)
from api.services.admin_resource_service import (
    AdminAspcService,
    AdminGenelistService,
    AdminPanelService,
    AdminSampleService,
    AdminSchemaService,
)
from api.services.admin_role_service import AdminRoleService
from api.services.admin_user_service import AdminUserService
from api.services.biomarker_service import BiomarkerService
from api.services.cnv_service import CnvService
from api.services.coverage_service import CoverageService
from api.services.dashboard_service import DashboardService
from api.services.dna_service import DnaService
from api.services.dna_structural_service import DnaStructuralService
from api.services.fusion_service import FusionService
from api.services.permission_management_service import PermissionManagementService
from api.services.report_service import ReportService
from api.services.resource_annotation_service import ResourceAnnotationService
from api.services.resource_classification_service import ResourceClassificationService
from api.services.rna_service import RnaService
from api.services.sample_catalog_service import SampleCatalogService
from api.services.sample_service import SampleService
from api.services.small_variant_service import SmallVariantService
from api.services.translocation_service import TranslocationService
from api.services.user_service import UserService


@lru_cache
def get_admin_user_service() -> AdminUserService:
    """Return the shared admin user-management service.

    Returns:
        The service used by user-management routes.
    """
    return AdminUserService(repository=get_admin_repository())


@lru_cache
def get_admin_role_service() -> AdminRoleService:
    """Return the shared admin role-management service.

    Returns:
        The service used by role-management routes.
    """
    return AdminRoleService(repository=get_admin_repository())


@lru_cache
def get_permission_management_service() -> PermissionManagementService:
    """Return the shared permission-management service.

    Returns:
        The service used by permission-management routes.
    """
    return PermissionManagementService(repository=get_admin_repository())


@lru_cache
def get_admin_panel_service() -> AdminPanelService:
    """Return the shared assay-panel management service.

    Returns:
        The service used by ASP resource routes.
    """
    return AdminPanelService(repository=get_admin_repository())


@lru_cache
def get_admin_genelist_service() -> AdminGenelistService:
    """Return the shared genelist management service.

    Returns:
        The service used by genelist resource routes.
    """
    return AdminGenelistService(repository=get_admin_repository())


@lru_cache
def get_admin_aspc_service() -> AdminAspcService:
    """Return the shared assay-configuration management service.

    Returns:
        The service used by ASPC resource routes.
    """
    return AdminAspcService(repository=get_admin_repository())


@lru_cache
def get_admin_sample_service() -> AdminSampleService:
    """Return the shared admin sample-management service.

    Returns:
        The service used by admin sample routes.
    """
    return AdminSampleService(repository=get_admin_repository())


@lru_cache
def get_admin_schema_service() -> AdminSchemaService:
    """Return the shared schema-management service.

    Returns:
        The service used by schema resource routes.
    """
    return AdminSchemaService(repository=get_admin_repository())


@lru_cache
def get_coverage_service() -> CoverageService:
    """Return the shared coverage service.

    Returns:
        The service used by coverage routes.
    """
    return CoverageService(
        repository=get_coverage_repository(),
        processing_repository=get_coverage_processing_repository(),
    )


@lru_cache
def get_dashboard_service() -> DashboardService:
    """Return the shared dashboard service.

    Returns:
        The service used by dashboard routes.
    """
    return DashboardService(repository=get_dashboard_repository())


def get_dna_service() -> DnaService:
    """Return the DNA orchestration service.

    Returns:
        The service used by shared DNA workflows.
    """
    return DnaService(repository=get_dna_repository())


def get_small_variant_service() -> SmallVariantService:
    """Return the small-variant service.

    Returns:
        The service used by small-variant routes.
    """
    return SmallVariantService(repository=get_dna_repository())


def get_biomarker_service() -> BiomarkerService:
    """Return the biomarker service.

    Returns:
        The service used by biomarker routes.
    """
    return BiomarkerService(repository=get_dna_repository())


def get_classification_service() -> ResourceClassificationService:
    """Return the shared resource-classification service.

    Returns:
        The service used by classification routes.
    """
    return ResourceClassificationService(repository=get_dna_repository())


def get_resource_annotation_service() -> ResourceAnnotationService:
    """Return the shared resource-annotation service.

    Returns:
        The service used by annotation routes.
    """
    return ResourceAnnotationService(repository=get_dna_repository())


@lru_cache
def get_sample_catalog_service() -> SampleCatalogService:
    """Return the shared sample-catalog service.

    Returns:
        The service used by sample list and sample context routes.
    """
    return SampleCatalogService(repository=get_home_repository())


def get_rna_service() -> RnaService:
    """Return the RNA orchestration service.

    Returns:
        The service used by shared RNA workflows.
    """
    return RnaService(
        repository=get_rna_repository(),
        workflow_repository=get_rna_workflow_repository(),
    )


def get_fusion_service() -> FusionService:
    """Return the fusion service.

    Returns:
        The service used by fusion routes.
    """
    return FusionService(
        repository=get_rna_repository(),
        workflow_repository=get_rna_workflow_repository(),
    )


def get_dna_structural_service() -> DnaStructuralService:
    """Return the DNA structural service.

    Returns:
        The service used by structural DNA workflows.
    """
    return DnaStructuralService(repository=get_dna_repository())


def get_cnv_service() -> CnvService:
    """Return the CNV service.

    Returns:
        The service used by CNV routes.
    """
    return CnvService(repository=get_dna_repository())


def get_translocation_service() -> TranslocationService:
    """Return the translocation service.

    Returns:
        The service used by translocation routes.
    """
    return TranslocationService(repository=get_dna_repository())


@lru_cache
def get_report_service() -> ReportService:
    """Return the shared report service.

    Returns:
        The service used by report preview and save routes.
    """
    return ReportService()


def get_user_service() -> UserService:
    """Return the user service.

    Returns:
        The service used by non-admin user flows.
    """
    return UserService()


def get_sample_service() -> SampleService:
    """Return the sample service.

    Returns:
        The service used by sample mutation routes.
    """
    return SampleService()
