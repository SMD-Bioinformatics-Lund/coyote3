"""Service dependency factories."""

from functools import lru_cache

from api.deps.handlers import get_store
from api.extensions import util
from api.infra.dashboard_cache import invalidate_dashboard_summary_cache
from api.services.accounts.permissions import PermissionManagementService
from api.services.accounts.roles import RoleManagementService
from api.services.accounts.user_profile import UserService
from api.services.accounts.users import UserManagementService
from api.services.biomarker.biomarker_lookup import BiomarkerService
from api.services.classification.tiering import ResourceClassificationService
from api.services.classification.variant_annotation import ResourceAnnotationService
from api.services.common.query_service import CommonQueryService
from api.services.dashboard.analytics import DashboardService
from api.services.dna.structural_variants import DnaStructuralService
from api.services.dna.variant_analysis import DnaService
from api.services.ingest.service import InternalIngestService
from api.services.public.catalog import PublicCatalogService
from api.services.reporting.dna_workflow import DNAWorkflowService
from api.services.reporting.report_builder import ReportService
from api.services.reporting.rna_workflow import RNAWorkflowService
from api.services.resources.asp import AspService
from api.services.resources.aspc import AspcService
from api.services.resources.isgl import IsglService
from api.services.resources.sample import ResourceSampleService
from api.services.rna.expression_analysis import RnaService
from api.services.sample.catalog import SampleCatalogService
from api.services.sample.coverage import CoverageService
from api.services.sample.sample_lookup import SampleService


@lru_cache
def get_admin_user_service() -> UserManagementService:
    """Return the shared admin user-management service."""
    return UserManagementService.from_store(get_store(), common_util=util.common)


@lru_cache
def get_admin_role_service() -> RoleManagementService:
    """Return the shared admin role-management service."""
    return RoleManagementService.from_store(get_store())


@lru_cache
def get_permission_management_service() -> PermissionManagementService:
    """Return the shared permission-management service."""
    return PermissionManagementService.from_store(get_store())


@lru_cache
def get_admin_panel_service() -> AspService:
    """Return the shared assay-panel management service."""
    return AspService.from_store(get_store())


@lru_cache
def get_admin_genelist_service() -> IsglService:
    """Return the shared genelist management service."""
    return IsglService.from_store(get_store())


@lru_cache
def get_admin_aspc_service() -> AspcService:
    """Return the shared assay-configuration management service."""
    return AspcService.from_store(get_store(), common_util=util.common)


@lru_cache
def get_admin_sample_service() -> ResourceSampleService:
    """Return the shared admin sample-management service."""
    return ResourceSampleService.from_store(get_store(), records_util=util.records)


@lru_cache
def get_coverage_service() -> CoverageService:
    """Return the shared coverage service."""
    return CoverageService.from_store(get_store())


@lru_cache
def get_dashboard_service() -> DashboardService:
    """Return the shared dashboard service."""
    return DashboardService.from_store(get_store())


def get_dna_service() -> DnaService:
    """Return the DNA orchestration service."""
    return DnaService.from_store(get_store())


def get_biomarker_service() -> BiomarkerService:
    """Return the biomarker service."""
    return BiomarkerService.from_store(get_store())


def get_classification_service() -> ResourceClassificationService:
    """Return the shared resource-classification service."""
    return ResourceClassificationService.from_store(get_store())


def get_resource_annotation_service() -> ResourceAnnotationService:
    """Return the shared resource-annotation service."""
    return ResourceAnnotationService.from_store(get_store())


@lru_cache
def get_sample_catalog_service() -> SampleCatalogService:
    """Return the shared sample-catalog service."""
    return SampleCatalogService.from_store(get_store())


def get_rna_service() -> RnaService:
    """Return the RNA orchestration service."""
    return RnaService.from_store(get_store())


def get_dna_structural_service() -> DnaStructuralService:
    """Return the DNA structural service."""
    return DnaStructuralService.from_store(get_store())


@lru_cache
def get_report_service() -> ReportService:
    """Return the shared report service."""
    return ReportService()


def get_user_service() -> UserService:
    """Return the user service."""
    return UserService.from_store(get_store())


def get_common_query_service() -> CommonQueryService:
    """Return the common query service."""
    return CommonQueryService.from_store(get_store())


def get_sample_service() -> SampleService:
    """Return the sample service."""
    return SampleService.from_store(get_store())


@lru_cache
def get_public_catalog_service() -> PublicCatalogService:
    """Return the shared public catalog service."""
    return PublicCatalogService.from_store(get_store())


def get_rna_workflow_service() -> RNAWorkflowService:
    """Return the RNA reporting workflow service."""
    return RNAWorkflowService.from_store(get_store())


def get_dna_workflow_service() -> DNAWorkflowService:
    """Return the DNA reporting workflow service."""
    return DNAWorkflowService.from_store(get_store())


def get_internal_ingest_service() -> InternalIngestService:
    """Return the internal ingest service."""
    return InternalIngestService.from_store(
        get_store(),
        dashboard_summary_cache_invalidator=invalidate_dashboard_summary_cache,
    )
