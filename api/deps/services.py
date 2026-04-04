"""Service dependency factories."""

from functools import lru_cache

from api.services.accounts.permissions import PermissionManagementService
from api.services.accounts.roles import RoleManagementService
from api.services.accounts.user_profile import UserService
from api.services.accounts.users import UserManagementService
from api.services.biomarker.biomarker_lookup import BiomarkerService
from api.services.classification.tiering import ResourceClassificationService
from api.services.classification.variant_annotation import ResourceAnnotationService
from api.services.dashboard.analytics import DashboardService
from api.services.dna.cnv import CnvService
from api.services.dna.small_variants import SmallVariantService
from api.services.dna.structural_variants import DnaStructuralService
from api.services.dna.translocations import TranslocationService
from api.services.dna.variant_analysis import DnaService
from api.services.reporting.report_builder import ReportService
from api.services.resources.asp import AspService
from api.services.resources.aspc import AspcService, QueryProfileService
from api.services.resources.isgl import IsglService
from api.services.resources.sample import ResourceSampleService
from api.services.rna.expression_analysis import RnaService
from api.services.rna.fusions import FusionService
from api.services.sample.catalog import SampleCatalogService
from api.services.sample.coverage import CoverageService
from api.services.sample.sample_lookup import SampleService


@lru_cache
def get_admin_user_service() -> UserManagementService:
    """Return the shared admin user-management service."""
    return UserManagementService()


@lru_cache
def get_admin_role_service() -> RoleManagementService:
    """Return the shared admin role-management service."""
    return RoleManagementService()


@lru_cache
def get_permission_management_service() -> PermissionManagementService:
    """Return the shared permission-management service."""
    return PermissionManagementService()


@lru_cache
def get_admin_panel_service() -> AspService:
    """Return the shared assay-panel management service."""
    return AspService()


@lru_cache
def get_admin_genelist_service() -> IsglService:
    """Return the shared genelist management service."""
    return IsglService()


@lru_cache
def get_admin_aspc_service() -> AspcService:
    """Return the shared assay-configuration management service."""
    return AspcService()


@lru_cache
def get_admin_sample_service() -> ResourceSampleService:
    """Return the shared admin sample-management service."""
    return ResourceSampleService()


@lru_cache
def get_admin_query_profile_service() -> QueryProfileService:
    """Return the shared query-profile options service."""
    return QueryProfileService()


@lru_cache
def get_coverage_service() -> CoverageService:
    """Return the shared coverage service."""
    return CoverageService()


@lru_cache
def get_dashboard_service() -> DashboardService:
    """Return the shared dashboard service."""
    return DashboardService()


def get_dna_service() -> DnaService:
    """Return the DNA orchestration service."""
    return DnaService()


def get_small_variant_service() -> SmallVariantService:
    """Return the small-variant service."""
    return SmallVariantService()


def get_biomarker_service() -> BiomarkerService:
    """Return the biomarker service."""
    return BiomarkerService()


def get_classification_service() -> ResourceClassificationService:
    """Return the shared resource-classification service."""
    return ResourceClassificationService()


def get_resource_annotation_service() -> ResourceAnnotationService:
    """Return the shared resource-annotation service."""
    return ResourceAnnotationService()


@lru_cache
def get_sample_catalog_service() -> SampleCatalogService:
    """Return the shared sample-catalog service."""
    return SampleCatalogService()


def get_rna_service() -> RnaService:
    """Return the RNA orchestration service."""
    return RnaService()


def get_fusion_service() -> FusionService:
    """Return the fusion service."""
    return FusionService()


def get_dna_structural_service() -> DnaStructuralService:
    """Return the DNA structural service."""
    return DnaStructuralService()


def get_cnv_service() -> CnvService:
    """Return the CNV service."""
    return CnvService()


def get_translocation_service() -> TranslocationService:
    """Return the translocation service."""
    return TranslocationService()


@lru_cache
def get_report_service() -> ReportService:
    """Return the shared report service."""
    return ReportService()


def get_user_service() -> UserService:
    """Return the user service."""
    return UserService()


def get_sample_service() -> SampleService:
    """Return the sample service."""
    return SampleService()
