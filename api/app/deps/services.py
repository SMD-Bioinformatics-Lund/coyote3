"""Service dependency factories."""

from functools import lru_cache, partial
from typing import TypeVar
from urllib.parse import urlsplit

from api.app.container import util
from api.app.deps.repositories import get_store
from api.app.runtime_state import app as runtime_app
from api.config.security import (
    get_api_session_ttl_seconds,
    get_api_sessions_collection_name,
    get_audit_events_collection_name,
)
from api.contracts.deployment_data import DeploymentDataScope
from api.infra.external_sort import sorted_page
from api.infra.notifications.email import send_email, smtp_configured
from api.infra.observability.logging import current_request_context
from api.infra.observability.prometheus_metrics import observe_operation
from api.infra.report_images import get_plot
from api.infra.security.sessions import MongoApiSessionRepository
from api.services.provisioning.demo_installation import DemoInstallationService
from api.services.provisioning.deployment_data import DeploymentDataService
from coyote3.application.accounts.permissions import PermissionManagementService
from coyote3.application.accounts.roles import RoleManagementService
from coyote3.application.accounts.users import UserManagementService
from coyote3.application.admin.app_controls import (
    AppControlsService,
    effective_audit_retention_days,
)
from coyote3.application.audit.service import AuditService
from coyote3.application.biomarker.biomarker_lookup import BiomarkerService
from coyote3.application.classification.tiering import ResourceClassificationService
from coyote3.application.classification.variant_annotation import ResourceAnnotationService
from coyote3.application.common.query_service import CommonQueryService
from coyote3.application.dashboard.analytics import DashboardService
from coyote3.application.dashboard.cache import invalidate_dashboard_metrics
from coyote3.application.dna.structural_variants import DnaStructuralService
from coyote3.application.dna.variant_analysis import DnaService
from coyote3.application.ingest.service import InternalIngestService
from coyote3.application.knowledgebase.oncokb_refresh import PublicOncoKbRefreshService
from coyote3.application.knowledgebase.public_variants import PublicVariantAnnotations
from coyote3.application.notifications.access import SampleNotificationAccess
from coyote3.application.notifications.activity import ActivityNotificationService
from coyote3.application.notifications.service import NotificationService
from coyote3.application.public.catalog import PublicCatalogService
from coyote3.application.query_rules.service import QueryRuleService
from coyote3.application.query_rules.testing import QueryRuleTestingService
from coyote3.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
from coyote3.application.reporting.clinical_rules.testing import ClinicalRuleTestingService
from coyote3.application.reporting.dna_workflow import DNAWorkflowService
from coyote3.application.reporting.report_library import ReportLibraryService
from coyote3.application.reporting.rna_workflow import RNAWorkflowService
from coyote3.application.resources.asp import AspService
from coyote3.application.resources.aspc import AspcService
from coyote3.application.resources.assay_groups import AssayGroupService
from coyote3.application.resources.assay_setup import AssaySetupService
from coyote3.application.resources.configuration_profiles import ConfigurationProfileService
from coyote3.application.resources.configuration_promotions import ConfigurationPromotionService
from coyote3.application.resources.diagnoses import DiagnosisService
from coyote3.application.resources.fields import ResourceFieldService
from coyote3.application.resources.isgl import IsglService
from coyote3.application.resources.public_assay_catalog import PublicAssayCatalogManagementService
from coyote3.application.resources.sample import ResourceSampleService
from coyote3.application.rna.expression_analysis import RnaService
from coyote3.application.sample.catalog import SampleCatalogService
from coyote3.application.sample.coverage import CoverageService
from coyote3.config.policy import get_runtime_environment

ServiceT = TypeVar("ServiceT")


def _observed(service: ServiceT) -> ServiceT:
    """Attach the deployment metrics adapter to an application service.

    Args:
        service: Constructed application service with measured operations.

    Returns:
        The same service, observing metrics without importing collectors in the core.
    """
    setattr(service, "operation_observer", observe_operation)
    return service


@lru_cache
def get_admin_user_service() -> UserManagementService:
    """Return the admin user-management service."""
    from api.security.password_flows import issue_password_token_for_user, notify_user_change

    return UserManagementService.from_store(
        get_store(),
        common_util=util.common,
        password_token_issuer=issue_password_token_for_user,
        user_change_notifier=notify_user_change,
    )


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


def get_admin_diagnosis_service() -> DiagnosisService:
    """Build the assay-owned diagnosis management service."""
    return DiagnosisService.from_store(get_store())


def get_admin_assay_group_service() -> AssayGroupService:
    """Build registry administration against the operational database."""
    return AssayGroupService(get_store().assay_group_repository)


def get_assay_setup_service() -> AssaySetupService:
    """Build the governed draft-first assay setup service."""
    return AssaySetupService(get_store(), common_util=util.common)


@lru_cache
def get_admin_genelist_service() -> IsglService:
    """Return the genelist management service."""
    return IsglService.from_store(get_store())


@lru_cache
def get_admin_aspc_service() -> AspcService:
    """Return the assay-configuration management service."""
    return AspcService.from_store(get_store())


@lru_cache
def get_configuration_profile_service() -> ConfigurationProfileService:
    """Return reusable source-profile authoring and publication workflows."""
    return ConfigurationProfileService(get_store().configuration_profile_repository)


@lru_cache
def get_configuration_promotion_service() -> ConfigurationPromotionService:
    """Return exact-source environment promotion and independent approval workflows."""
    store = get_store()
    return ConfigurationPromotionService(
        store.configuration_profile_repository, store.assay_configuration_repository
    )


@lru_cache
def get_admin_sample_service() -> ResourceSampleService:
    """Return the admin sample-management service."""
    from api.infra.mongo.repositories.sample_deletion import SampleDeletionRepository

    store = get_store()
    deletion = SampleDeletionRepository(
        store, reports_root=runtime_app.config.get("REPORTS_BASE_PATH", "reports")
    )
    return _observed(ResourceSampleService.from_store(store, sample_deleter=deletion.delete))


@lru_cache
def get_resource_field_service() -> ResourceFieldService:
    """Return individual read-only metadata fields for service-facing resource lookups."""
    return ResourceFieldService.from_store(get_store())


def get_admin_public_assay_catalog_service() -> PublicAssayCatalogManagementService:
    """Return the public assay catalog administration service."""
    service = PublicAssayCatalogManagementService.from_store(get_store())
    service.notification_service = get_notification_service()
    return service


@lru_cache
def get_coverage_service() -> CoverageService:
    """Return the coverage service."""
    return CoverageService.from_store(get_store())


@lru_cache
def get_dashboard_service() -> DashboardService:
    """Return the dashboard service."""
    return _observed(
        DashboardService.from_store(
            get_store(),
            config=runtime_app.config,
        )
    )


def get_dna_service() -> DnaService:
    """Return the DNA orchestration service."""
    return _observed(DnaService.from_store(get_store()))


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
    return _observed(
        SampleCatalogService.from_store(
            get_store(),
            reports_base_path=runtime_app.config.get("REPORTS_BASE_PATH", ""),
        )
    )


def get_rna_service() -> RnaService:
    """Return the RNA orchestration service."""
    return RnaService.from_store(get_store(), page_sorter=sorted_page)


def get_dna_structural_service() -> DnaStructuralService:
    """Return the DNA structural service."""
    return DnaStructuralService.from_store(get_store(), page_sorter=sorted_page)


def get_report_library_service() -> ReportLibraryService:
    """Return the read-only saved report library service."""
    return ReportLibraryService.from_store(get_store())


def get_clinical_rule_authoring_service() -> ClinicalRuleAuthoringService:
    """Return the governed clinical rule authoring service."""
    service = ClinicalRuleAuthoringService.from_store(get_store())
    service.notification_service = get_notification_service()
    return service


def get_query_rule_service() -> QueryRuleService:
    """Bind query-rule authoring and resolution to the application repositories."""
    return QueryRuleService.from_store(get_store())


def get_query_rule_testing_service() -> QueryRuleTestingService:
    """Return the read-only stored-sample query comparison service."""
    return QueryRuleTestingService(get_store())


def get_clinical_rule_testing_service() -> ClinicalRuleTestingService:
    """Return the read-only clinical rule sample-testing service."""
    return ClinicalRuleTestingService.from_store(get_store())


def get_common_query_service() -> CommonQueryService:
    """Return the common query service."""
    return _observed(CommonQueryService.from_store(get_store()))


@lru_cache
def get_public_catalog_service() -> PublicCatalogService:
    """Return the public catalog service."""
    return PublicCatalogService.from_store(get_store())


def get_rna_workflow_service() -> RNAWorkflowService:
    """Return the RNA reporting workflow service."""
    return RNAWorkflowService.from_store(get_store())


def get_dna_workflow_service() -> DNAWorkflowService:
    """Return the DNA reporting workflow service."""
    return DNAWorkflowService.from_store(get_store(), plot_reader=get_plot)


def get_internal_ingest_service() -> InternalIngestService:
    """Return the internal ingest service."""
    from api.infra.mongo.repositories.ingest_gateway import IngestCollectionGateway

    store = get_store()
    return InternalIngestService.from_store(
        store,
        collection_gateway=IngestCollectionGateway.from_store(store),
        dashboard_metrics_invalidator=invalidate_dashboard_metrics,
        audit_service=get_audit_service(),
        notification_service=get_notification_service(),
        monitoring_group=str(runtime_app.config.get("ERROR_EMAIL_GROUP") or "monitoring_group"),
    )


def get_demo_installation_service() -> DemoInstallationService:
    """Bind the private demonstration installer to application storage and normal ingest."""
    from api.config.paths import DEMO_WORKFLOW_BUNDLE_PATH
    from api.infra.mongo.repositories.demo_installation import DemoInstallationRepository

    return DemoInstallationService(
        DemoInstallationRepository(get_store().coyote_db),
        get_internal_ingest_service(),
        bundle=DEMO_WORKFLOW_BUNDLE_PATH,
        identifier_factory=DemoInstallationRepository.identifier,
    )


def get_api_session_repository() -> MongoApiSessionRepository:
    """Return the Mongo-backed API session repository."""
    from api.security.access import api_user_from_user_doc

    store = get_store()
    collection = store.identity_db[get_api_sessions_collection_name(runtime_app.config)]

    def _load_user(username: str):
        """Load an active user's API identity for session resolution.

        Args:
            username: User document ID to retrieve from the shared user repository.

        Returns:
            An API user, or None if the document is absent or is_active is falsy.
            A missing is_active flag is treated as active.
        """
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
    if store.identity_db is None:
        return None
    from pathlib import Path

    from pymongo.write_concern import WriteConcern

    from api.infra.mongo.repositories.audit import AuditRepository
    from api.infra.mongo.repositories.audit_outbox import AuditOutboxRepository, audit_route

    environment = get_runtime_environment(runtime_app.config)
    namespace = audit_route(runtime_app.config)
    return AuditService(
        AuditRepository(
            store.identity_db[get_audit_events_collection_name(runtime_app.config)].with_options(
                write_concern=WriteConcern("majority", j=True)
            ),
            outbox_route=namespace,
            outboxes=tuple(
                AuditOutboxRepository(db)
                for db in (
                    store.coyote_db,
                    store.identity_db,
                    store.knowledgebase_db,
                )
                if db is not None
            ),
            spool_directory=Path(runtime_app.config.get("LOG_ROOT") or "logs")
            / "audit-spool"
            / namespace,
        ),
        retention_days=effective_audit_retention_days(
            get_app_controls_repository(), runtime_app.config
        ),
        environment=environment,
        request_context=current_request_context,
    )


def get_deployment_data_service() -> DeploymentDataService:
    """Build the authenticated deployment-data service using the existing packaged seed loaders."""
    from api.infra.mongo.repositories.deployment_data import DeploymentDataRepository
    from api.infra.seed.diagrams import load_seed_diagrams
    from api.infra.seed.documents import (
        DEFAULT_RBAC_DIR,
        DEFAULT_REFERENCE_DIR,
        build_seed_documents,
    )

    def load(actor: str, scope: DeploymentDataScope) -> dict[str, list[dict]]:
        """Validate packaged catalogs and stamp them with the authenticated installer identity."""
        documents = build_seed_documents(
            rbac_dir=DEFAULT_RBAC_DIR,
            reference_dir=DEFAULT_REFERENCE_DIR,
            actor=actor,
            include_knowledgebase=scope != "application",
        )
        if scope != "application":
            documents["vep_diagrams"] = load_seed_diagrams(
                documents["vep_metadata"], DEFAULT_REFERENCE_DIR
            )
        return documents

    store = get_store()
    return DeploymentDataService(
        DeploymentDataRepository(store.coyote_db, store.knowledgebase_db, store.identity_db),
        load,
        get_demo_installation_service(),
    )


def get_email_config() -> dict:
    """Combine SMTP settings with the current application email switch."""
    return {
        **runtime_app.config,
        "EMAIL_ENABLED": get_app_controls_service().get_controls().email.enabled,
    }


def get_activity_notification_service() -> ActivityNotificationService:
    """Return the committed-activity notification delivery service."""
    from api.infra.mongo.repositories.notification_activity import NotificationActivityRepository

    store = get_store()
    return ActivityNotificationService.from_store(
        store,
        config=runtime_app.config,
        activity_repository=NotificationActivityRepository.from_store(
            store, config=runtime_app.config
        ),
        sample_access=get_sample_notification_access(),
    )


def get_sample_notification_access() -> SampleNotificationAccess:
    """Bind notification scope resolution to the configured authorization engine."""
    from api.security.policy import build_access_policy

    return SampleNotificationAccess.from_store(get_store(), policy_factory=build_access_policy)


def get_notification_service() -> NotificationService:
    """Return the recipient-scoped notification service."""
    config = get_email_config()
    base = str(config.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    prefix = str(config.get("SCRIPT_NAME") or "").strip().rstrip("/")
    url = urlsplit(base)
    email_ready = smtp_configured(config) and url.scheme in {"http", "https"} and bool(url.netloc)
    return NotificationService.from_store(
        get_store(),
        retention_days=int(runtime_app.config.get("NOTIFICATION_RETENTION_DAYS", 180)),
        sample_access=get_sample_notification_access(),
        audit_service=get_audit_service(),
        email_sender=partial(send_email, config=config) if email_ready else None,
        inbox_url=f"{base}{prefix}/notifications" if email_ready else "",
    )


def get_app_controls_service() -> AppControlsService:
    """Return the DB-backed application controls service."""
    store = get_store()
    from api.infra.mongo.repositories.report_artifact_erasure import report_erasure_backlog
    from api.infra.operational_runtime import cleanup_disk_logs

    return AppControlsService(
        get_app_controls_repository(),
        config=runtime_app.config,
        runtime_inspector=inspect_task_runtime,
        log_cleanup=cleanup_disk_logs,
        audit_service=get_audit_service(),
        index_conflicts_provider=lambda: getattr(
            getattr(store, "_adapter", None), "index_setup_conflicts", []
        ),
        erasure_status_provider=lambda: report_erasure_backlog(store.coyote_db),
    )


def get_app_controls_repository():
    """Bind controls and audit retention to their independently configured databases."""
    from api.infra.mongo.repositories.app_controls import MongoAppControlsRepository

    store = get_store()
    return MongoAppControlsRepository(
        store.coyote_db, identity_db=store.identity_db, config=runtime_app.config
    )


def inspect_task_runtime(*, enabled: bool, timeout: float) -> dict:
    """Bind the Celery runtime only when worker inspection is requested.

    Args:
        enabled: Whether controls permit application task execution.
        timeout: Worker inspection timeout in seconds.

    Returns:
        Observed worker and scheduler status from the infrastructure adapter.
    """
    from api.celery_app import celery_app
    from api.infra.operational_runtime import inspect_celery_runtime

    return inspect_celery_runtime(celery_app, enabled=enabled, timeout=timeout)


def get_public_oncokb_refresh_service() -> PublicOncoKbRefreshService:
    """Return the HGNC-backed public OncoKB reference refresh service."""
    from api.infra.knowledgebase.public_oncokb import PublicOncoKbClient

    return PublicOncoKbRefreshService.from_store(
        get_store(),
        config=runtime_app.config,
        client=PublicOncoKbClient(
            base_url=str(runtime_app.config["ONCOKB_BASE_URL"]),
            timeout=float(runtime_app.config.get("ONCOKB_REQUEST_TIMEOUT_SECONDS", 3.0) or 3.0),
        ),
        audit_service=get_audit_service(),
    )


def get_public_variant_annotations() -> PublicVariantAnnotations:
    """Bind on-demand public lookups, current feature switches and local accession reads."""
    from api.infra.knowledgebase.clinpgx_public import ClinPgxPublicClient
    from api.infra.knowledgebase.public_oncokb import PublicOncoKbClient
    from api.infra.knowledgebase.variant_lookups import PublicVariantLookups

    clients = PublicVariantLookups(
        oncokb=PublicOncoKbClient(
            base_url=runtime_app.config["ONCOKB_BASE_URL"],
            timeout=float(runtime_app.config.get("ONCOKB_REQUEST_TIMEOUT_SECONDS", 3.0)),
        ),
        clinpgx=ClinPgxPublicClient(
            base_url=runtime_app.config["CLINPGX_BASE_URL"],
            timeout=float(runtime_app.config.get("CLINPGX_REQUEST_TIMEOUT_SECONDS", 3.0)),
        ),
    )
    repository = get_dna_service().clinpgx_public_repository
    return PublicVariantAnnotations(
        oncokb_enabled=bool(runtime_app.config.get("ONCOKB_PUBLIC_LOOKUPS_ENABLED", True)),
        clinpgx_enabled=bool(runtime_app.config.get("CLINPGX_PUBLIC_LOOKUPS_ENABLED", True)),
        oncokb_lookup=clients.oncokb,
        clinpgx_lookup=clients.clinpgx,
        local_gene_lookup=lambda symbol: (
            repository.get_gene_record(symbol) if repository is not None else None
        ),
    )
