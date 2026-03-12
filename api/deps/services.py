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
from api.services.permission_management_service import PermissionManagementService
from api.services.admin_resource_service import (
    AdminAspcService,
    AdminGenelistService,
    AdminPanelService,
    AdminSampleService,
    AdminSchemaService,
)
from api.services.admin_role_service import AdminRoleService
from api.services.admin_user_service import AdminUserService
from api.services.resource_annotation_service import ResourceAnnotationService
from api.services.biomarker_service import BiomarkerService
from api.services.resource_classification_service import ResourceClassificationService
from api.services.cnv_service import CnvService
from api.services.coverage_service import CoverageService
from api.services.dashboard_service import DashboardService
from api.services.dna_service import DnaService
from api.services.dna_structural_service import DnaStructuralService
from api.services.fusion_service import FusionService
from api.services.sample_catalog_service import SampleCatalogService
from api.services.report_service import ReportService
from api.services.rna_service import RnaService
from api.services.sample_service import SampleService
from api.services.small_variant_service import SmallVariantService
from api.services.translocation_service import TranslocationService
from api.services.user_service import UserService


@lru_cache
def get_admin_user_service() -> AdminUserService:
    return AdminUserService(repository=get_admin_repository())


@lru_cache
def get_admin_role_service() -> AdminRoleService:
    return AdminRoleService(repository=get_admin_repository())


@lru_cache
def get_permission_management_service() -> PermissionManagementService:
    return PermissionManagementService(repository=get_admin_repository())


@lru_cache
def get_admin_panel_service() -> AdminPanelService:
    return AdminPanelService(repository=get_admin_repository())


@lru_cache
def get_admin_genelist_service() -> AdminGenelistService:
    return AdminGenelistService(repository=get_admin_repository())


@lru_cache
def get_admin_aspc_service() -> AdminAspcService:
    return AdminAspcService(repository=get_admin_repository())


@lru_cache
def get_admin_sample_service() -> AdminSampleService:
    return AdminSampleService(repository=get_admin_repository())


@lru_cache
def get_admin_schema_service() -> AdminSchemaService:
    return AdminSchemaService(repository=get_admin_repository())


@lru_cache
def get_coverage_service() -> CoverageService:
    return CoverageService(
        repository=get_coverage_repository(),
        processing_repository=get_coverage_processing_repository(),
    )


@lru_cache
def get_dashboard_service() -> DashboardService:
    return DashboardService(repository=get_dashboard_repository())


def get_dna_service() -> DnaService:
    return DnaService(repository=get_dna_repository())


def get_small_variant_service() -> SmallVariantService:
    return SmallVariantService(repository=get_dna_repository())


def get_biomarker_service() -> BiomarkerService:
    return BiomarkerService(repository=get_dna_repository())


def get_classification_service() -> ResourceClassificationService:
    return ResourceClassificationService(repository=get_dna_repository())


def get_resource_annotation_service() -> ResourceAnnotationService:
    return ResourceAnnotationService(repository=get_dna_repository())


@lru_cache
def get_sample_catalog_service() -> SampleCatalogService:
    return SampleCatalogService(repository=get_home_repository())


def get_rna_service() -> RnaService:
    return RnaService(
        repository=get_rna_repository(),
        workflow_repository=get_rna_workflow_repository(),
    )


def get_fusion_service() -> FusionService:
    return FusionService(
        repository=get_rna_repository(),
        workflow_repository=get_rna_workflow_repository(),
    )


def get_dna_structural_service() -> DnaStructuralService:
    return DnaStructuralService(repository=get_dna_repository())


def get_cnv_service() -> CnvService:
    return CnvService(repository=get_dna_repository())


def get_translocation_service() -> TranslocationService:
    return TranslocationService(repository=get_dna_repository())


@lru_cache
def get_report_service() -> ReportService:
    return ReportService()


def get_user_service() -> UserService:
    return UserService()


def get_sample_service() -> SampleService:
    return SampleService()
