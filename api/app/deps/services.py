"""Service dependency factories."""

from functools import lru_cache

from api.app.container import util
from api.app.deps.repositories import get_store
from api.app.runtime_state import app as runtime_app
from api.application.accounts.permissions import PermissionManagementService
from api.application.accounts.roles import RoleManagementService
from api.application.accounts.user_profile import UserService
from api.application.accounts.users import UserManagementService
from api.application.admin.app_controls import AppControlsService, effective_audit_retention_days
from api.application.audit.service import AuditService
from api.application.biomarker.biomarker_lookup import BiomarkerService
from api.application.classification.tiering import ResourceClassificationService
from api.application.classification.variant_annotation import ResourceAnnotationService
from api.application.common.query_service import CommonQueryService
from api.application.dashboard.analytics import DashboardService
from api.application.dna.structural_variants import DnaStructuralService
from api.application.dna.variant_analysis import DnaService
from api.application.ingest.service import InternalIngestService
from api.application.public.catalog import PublicCatalogService
from api.application.reporting.dna_workflow import DNAWorkflowService
from api.application.reporting.report_builder import ReportService
from api.application.reporting.rna_workflow import RNAWorkflowService
from api.application.resources.asp import AspService
from api.application.resources.aspc import AspcService
from api.application.resources.isgl import IsglService
from api.application.resources.sample import ResourceSampleService
from api.application.rna.expression_analysis import RnaService
from api.application.sample.catalog import SampleCatalogService
from api.application.sample.coverage import CoverageService
from api.application.sample.sample_lookup import SampleService
from api.infra.dashboard_cache import invalidate_dashboard_summary_cache
from api.infra.security.sessions import MongoApiSessionRepository
from api.settings import (
    get_api_session_ttl_seconds,
    get_api_sessions_collection_name,
    get_audit_events_collection_name,
    get_runtime_environment,
)


@lru_cache
def get_admin_user_service() -> UserManagementService:
    """Return the admin user-management service."""
    return UserManagementService.from_store(get_store(), common_util=util.common)


@lru_cache
def get_admin_role_service() -> RoleManagementService:
    """Return the admin role-management service."""
    return RoleManagementService.from_store(get_store())


@lru_cache
def get_permission_management_service() -> PermissionManagementService:
    """Return the permission-management service."""
    return PermissionManagementService.from_store(get_store())


@lru_cache
def get_admin_panel_service() -> AspService:
    """Return the assay-panel management service."""
    return AspService.from_store(get_store())


@lru_cache
def get_admin_genelist_service() -> IsglService:
    """Return the genelist management service."""
    return IsglService.from_store(get_store())


@lru_cache
def get_admin_aspc_service() -> AspcService:
    """Return the assay-configuration management service."""
    return AspcService.from_store(get_store(), common_util=util.common)


@lru_cache
def get_admin_sample_service() -> ResourceSampleService:
    """Return the admin sample-management service."""
    return ResourceSampleService.from_store(get_store(), records_util=util.records)


@lru_cache
def get_coverage_service() -> CoverageService:
    """Return the coverage service."""
    return CoverageService.from_store(get_store())


@lru_cache
def get_dashboard_service() -> DashboardService:
    """Return the dashboard service."""
    return DashboardService.from_store(
        get_store(),
        cache_backend=getattr(runtime_app, "cache", None),
        config=runtime_app.config,
    )


def get_dna_service() -> DnaService:
    """Return the DNA orchestration service."""
    return DnaService.from_store(get_store())


def get_biomarker_service() -> BiomarkerService:
    """Return the biomarker service."""
    return BiomarkerService.from_store(get_store())


def get_classification_service() -> ResourceClassificationService:
    """Return the resource-classification service."""
    return ResourceClassificationService.from_store(get_store())


def get_resource_annotation_service() -> ResourceAnnotationService:
    """Return the resource-annotation service."""
    return ResourceAnnotationService.from_store(get_store())


@lru_cache
def get_sample_catalog_service() -> SampleCatalogService:
    """Return the sample-catalog service."""
    return SampleCatalogService.from_store(
        get_store(),
        reported_samples_search_limit=runtime_app.config.get("REPORTED_SAMPLES_SEARCH_LIMIT", 50),
        reports_base_path=runtime_app.config.get("REPORTS_BASE_PATH", ""),
    )


def get_rna_service() -> RnaService:
    """Return the RNA orchestration service."""
    return RnaService.from_store(get_store())


def get_dna_structural_service() -> DnaStructuralService:
    """Return the DNA structural service."""
    return DnaStructuralService.from_store(get_store())


@lru_cache
def get_report_service() -> ReportService:
    """Return the report service."""
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
    """Return the public catalog service."""
    return PublicCatalogService.from_store(get_store())


def get_rna_workflow_service() -> RNAWorkflowService:
    """Return the RNA reporting workflow service."""
    return RNAWorkflowService.from_store(
        get_store(),
        report_config=runtime_app.config.get("REPORT_CONFIG", {}),
    )


def get_dna_workflow_service() -> DNAWorkflowService:
    """Return the DNA reporting workflow service."""
    return DNAWorkflowService.from_store(get_store())


def get_internal_ingest_service() -> InternalIngestService:
    """Return the internal ingest service."""
    return InternalIngestService.from_store(
        get_store(),
        dashboard_summary_cache_invalidator=invalidate_dashboard_summary_cache,
    )


def get_api_session_repository() -> MongoApiSessionRepository:
    """Return the Mongo-backed API session repository."""
    from api.security.access import api_user_from_user_doc

    store = get_store()
    collection = store.coyote_db[get_api_sessions_collection_name(runtime_app.config)]

    def _load_user(username: str):
        user_doc = store.user_repository.user_with_id(username)
        if not user_doc or not user_doc.get("is_active", True):
            return None
        return api_user_from_user_doc(user_doc)

    return MongoApiSessionRepository(
        collection,
        user_loader=_load_user,
        ttl_seconds=get_api_session_ttl_seconds(runtime_app.config),
    )


def get_audit_service() -> AuditService | None:
    """Return the durable Mongo-backed audit service when runtime is initialized."""
    store = get_store()
    if store.coyote_db is None:
        return None
    return AuditService(
        store.coyote_db[get_audit_events_collection_name(runtime_app.config)],
        retention_days=effective_audit_retention_days(store.coyote_db, runtime_app.config),
        environment=get_runtime_environment(runtime_app.config),
    )


def get_app_controls_service() -> AppControlsService:
    """Return the DB-backed application controls service."""
    return AppControlsService(
        get_store().coyote_db,
        config=runtime_app.config,
        audit_service=get_audit_service(),
    )
