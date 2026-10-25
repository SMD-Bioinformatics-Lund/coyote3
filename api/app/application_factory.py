"""Deployment composition for the in-process application SDK."""

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, Any

from coyote3.application.operations import (
    ApplicationRuntime,
    ApplicationServices,
    ClinicalServices,
    CoyoteApplication,
    ReportingServices,
)
from coyote3.application.operations.runtime import AccessEvent
from coyote3.domain.common.errors import api_error

if TYPE_CHECKING:
    from coyote3.application.ingest.service import InternalIngestService
    from coyote3.application.operations.account import PasswordRecovery
    from coyote3.application.operations.ingest import Ingestion, IngestSubmissionServices
    from coyote3.application.operations.internal_references import (
        InternalReferences,
        InternalReferenceServices,
    )
    from coyote3.application.operations.jobs import IngestJobExecution
    from coyote3.application.operations.maintenance import MaintenanceExecution
    from coyote3.application.operations.public import PublicApplication


def ingest_job_executor(
    service: "InternalIngestService", *, audit_access: Callable[[AccessEvent], None]
) -> "IngestJobExecution":
    """Compose a fixed worker capability for repository-loaded ingestion jobs.

    Args:
        service: Deployment ingestion service with its existing transaction boundary.
        audit_access: Worker access-audit sink; job and mutation audit remain service-owned.

    Returns:
        Job executor whose identity cannot read clinical resources or administer accounts.

    Notes:
        Only a trusted worker host calls this factory. Stored submitter metadata is
        attribution, not an authentication credential or a permission grant.
    """
    from api.infra.security.worker_policy import IngestWorkerIdentity, IngestWorkerPolicy
    from coyote3.application.operations.jobs import IngestJobExecution

    runtime = ApplicationRuntime(
        authenticate=IngestWorkerIdentity,
        allowed_operations=frozenset({"ingest.execute_job"}),
        policy_factory=lambda actor: IngestWorkerPolicy(),
        sample_loader=lambda identity: None,
        assay_loader=lambda identity: None,
        audit_access=audit_access,
    )
    return IngestJobExecution(runtime, service)


def application_services() -> ApplicationServices:
    """Bind the deployment's lazy use-case factories and report integration capabilities.

    Returns:
        Service factories using the initialized host runtime. No service is constructed here.
    """
    from api.app.deps.services import (
        get_admin_aspc_service,
        get_admin_assay_group_service,
        get_admin_diagnosis_service,
        get_admin_genelist_service,
        get_admin_panel_service,
        get_admin_public_assay_catalog_service,
        get_admin_role_service,
        get_admin_sample_service,
        get_admin_user_service,
        get_app_controls_service,
        get_assay_setup_service,
        get_audit_service,
        get_biomarker_service,
        get_classification_service,
        get_clinical_rule_authoring_service,
        get_clinical_rule_testing_service,
        get_common_query_service,
        get_configuration_profile_service,
        get_configuration_promotion_service,
        get_coverage_service,
        get_dashboard_service,
        get_dna_service,
        get_dna_structural_service,
        get_dna_workflow_service,
        get_internal_ingest_service,
        get_notification_service,
        get_permission_management_service,
        get_public_variant_annotations,
        get_query_rule_service,
        get_query_rule_testing_service,
        get_report_library_service,
        get_resource_annotation_service,
        get_resource_field_service,
        get_rna_service,
        get_rna_workflow_service,
        get_sample_catalog_service,
    )
    from api.app.http import get_formatted_assay_config
    from api.app.runtime_state import app
    from api.infra.registered_artifacts import FilesystemRegisteredArtifacts
    from api.presentation.reports.branding import render_branded_report_html
    from api.presentation.reports.modern import render_modern_report_html
    from coyote3.application.interpretation.report_summary import create_classified_variant_doc
    from coyote3.application.operations.administration import AdministrationServices
    from coyote3.application.operations.system import OperationsServices
    from coyote3.application.reporting.report_renderer import render_pdf_bytes
    from coyote3.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS

    return ApplicationServices(
        public=open_public_application,
        change_password=change_account_password,
        password_recovery=open_password_recovery,
        operations=OperationsServices(
            dashboard=get_dashboard_service,
            controls=get_app_controls_service,
            audit=get_audit_service,
            enqueue=enqueue_operation,
            issue_token=issue_ingest_credential,
            schemas=COLLECTION_MODEL_ADAPTERS,
        ),
        knowledgebase=get_common_query_service,
        knowledgebase_search_limit=int(app.config.get("TIERED_VARIANT_SEARCH_LIMIT", 1000)),
        notifications=get_notification_service,
        administration=AdministrationServices(
            users=get_admin_user_service,
            roles=get_admin_role_service,
            permissions=get_permission_management_service,
            assays=get_admin_panel_service,
            assay_groups=get_admin_assay_group_service,
            diagnoses=get_admin_diagnosis_service,
            assay_configurations=get_admin_aspc_service,
            gene_lists=get_admin_genelist_service,
            sample_administration=get_admin_sample_service,
            assay_setups=get_assay_setup_service,
            catalog_authoring=get_admin_public_assay_catalog_service,
            reference_data=get_resource_field_service,
        ),
        clinical=ClinicalServices(
            dna=get_dna_service,
            structural=get_dna_structural_service,
            rna=get_rna_service,
            classification=get_classification_service,
            classification_document=create_classified_variant_doc,
            annotations=get_resource_annotation_service,
            public_annotations=get_public_variant_annotations,
            catalog=get_sample_catalog_service,
            fields=get_resource_field_service,
            common_queries=get_common_query_service,
            coverage=get_coverage_service,
            biomarkers=get_biomarker_service,
            artifacts=FilesystemRegisteredArtifacts,
        ),
        reporting=ReportingServices(
            workflow=lambda analyte: (
                get_dna_workflow_service() if analyte == "dna" else get_rna_workflow_service()
            ),
            configuration=get_formatted_assay_config,
            render_html=partial(render_branded_report_html, config=app.config),
            organization_name=str(app.config.get("ORGANIZATION_NAME") or ""),
            reports_base_path=str(app.config.get("REPORTS_BASE_PATH") or "reports"),
            logger=app.logger,
            library=get_report_library_service,
            render_pdf=render_pdf_bytes,
            render_trial_html=partial(render_modern_report_html, branding_config=app.config),
        ),
        ingest=get_internal_ingest_service,
        ingest_submission=ingest_submission_services(),
        internal_references=internal_reference_services(),
        query_rules=get_query_rule_service,
        configuration_profiles=get_configuration_profile_service,
        configuration_promotions=get_configuration_promotion_service,
        clinical_rules=get_clinical_rule_authoring_service,
        query_rule_testing=get_query_rule_testing_service,
        clinical_rule_testing=get_clinical_rule_testing_service,
    )


def open_application(session_token: str, *, correlation_id: str | None = None) -> CoyoteApplication:
    """Bind SDK use cases to the host's revocable authenticated session.

    Args:
        session_token: Opaque token issued by existing authentication.
        correlation_id: Optional host request identity used by access auditing.

    Returns:
        Application resources with current identity, grants and sample-scope enforcement.
    """
    return CoyoteApplication(
        open_authenticated_runtime(session_token, correlation_id=correlation_id),
        application_services(),
    )


def open_authenticated_runtime(
    session_token: str, *, correlation_id: str | None = None
) -> ApplicationRuntime:
    """Bind a local application SDK to a revocable authenticated session.

    Args:
        session_token: Opaque session issued by existing authentication. It is resolved
            again on every operation; a username, role list or sample snapshot is insufficient.
        correlation_id: Optional host-generated correlation identity; None allocates one per call.

    Returns:
        Shared authorization and audit runtime for SDK and host-owned operations.

    Raises:
        ValueError: The session token is empty.

    Notes:
        The host initializes runtime infrastructure before calling this factory.
        This entry point is for a trusted process with infrastructure credentials.
        Untrusted notebooks and external automation use the HTTP client SDK.
    """
    if not session_token.strip():
        raise ValueError("An authenticated session token is required")
    from api.app.deps.repositories import (
        get_assay_panel_repository,
        get_permissions_repository,
        get_roles_repository,
        get_sample_repository,
    )
    from api.app.deps.services import get_api_session_repository
    from api.infra.mongo.records import application_result
    from api.security.policy import build_access_policy

    def authenticate() -> Any | None:
        """Reload an active session and its current user rather than retaining role claims."""
        session = get_api_session_repository().get(session_token)
        return session.user if session else None

    def load_sample(identity: str) -> dict[str, Any] | None:
        """Resolve a sample name or identifier through the configured repository."""
        repository = get_sample_repository()
        record = repository.get_sample(identity) or repository.get_sample_by_id(identity)
        return dict(record) if record else None

    runtime = ApplicationRuntime(
        authenticate=authenticate,
        policy_factory=lambda actor: build_access_policy(
            user=actor,
            roles_repository=get_roles_repository(),
            permissions_repository=get_permissions_repository(),
        ),
        sample_loader=load_sample,
        assay_loader=lambda identity: get_assay_panel_repository().get_asp(identity),
        audit_access=record_application_access,
        correlation_id=correlation_id,
        project_result=application_result,
    )
    return runtime


def enqueue_operation(operation: str, arguments: dict[str, Any]) -> str:
    """Publish a fixed operational task selected by trusted application code.

    Args:
        operation: dashboard, retention or oncokb; no arbitrary task names are accepted.
        arguments: Validated task inputs, including the current metric owner where needed.

    Returns:
        Broker task identifier.

    Raises:
        ValueError: The operation key is not registered.
    """
    from api.tasks.maintenance import (
        refresh_dashboard_metrics,
        refresh_public_oncokb,
        run_retention_maintenance,
    )

    tasks = {
        "dashboard": refresh_dashboard_metrics,
        "retention": run_retention_maintenance,
        "oncokb": refresh_public_oncokb,
    }
    if operation not in tasks:
        raise ValueError("Unknown application task")
    return str(tasks[operation].delay(**arguments).id)


def issue_ingest_credential(actor: Any, hours: int) -> dict[str, Any]:
    """Issue an audited fixed-environment credential using deployment signing capabilities.

    Args:
        actor: Current identity verified by the application runtime.
        hours: Requested expiry lifetime in hours.

    Returns:
        Signed ingestion credential and audited expiry metadata.
    """
    from api.app.deps.services import get_audit_service
    from api.app.runtime_state import app
    from api.config.security import get_internal_api_token
    from api.security.ingest_tokens import issue_token, verify_token
    from coyote3.application.ingest.tokens import issue_audited_ingest_token
    from coyote3.config.policy import get_runtime_environment

    return dict(
        issue_audited_ingest_token(
            token_issuer=issue_token,
            token_verifier=verify_token,
            secret=get_internal_api_token(app.config),
            environment=get_runtime_environment(app.config),
            hours=hours,
            actor=actor,
            audit=get_audit_service(),
        )
    )


def open_public_application() -> "PublicApplication":
    """Bind only the established anonymous published-catalog capability.

    Returns:
        Public metadata operations without clinical or mutation capabilities.
    """
    from api.app.deps.services import (
        get_app_controls_service,
        get_common_query_service,
        get_public_catalog_service,
    )
    from api.app.runtime_state import app
    from coyote3.application.operations.public import PublicApplication
    from coyote3.config.loaders.filter_flags import load_filter_flag_metadata

    return PublicApplication(
        catalog=get_public_catalog_service,
        controls=get_app_controls_service,
        config=app.config,
        logger=app.logger,
        filter_flags=load_filter_flag_metadata,
        gene_info=lambda identifier: dict(get_common_query_service().gene_info_payload(identifier)),
    )


def record_application_access(event: AccessEvent) -> None:
    """Persist a credential-free access decision before allowing application work."""
    from api.app.deps.services import get_audit_service

    service = get_audit_service()
    if service is None:
        raise api_error(503, "Application access audit is unavailable", category="setup")
    identity = service.record(
        "application.access",
        "Application operation authorized" if event.allowed else "Application operation denied",
        category="security",
        outcome="success" if event.allowed else "denied",
        actor=event.actor,
        resource_type="sample" if event.sample_id else None,
        resource_id=event.sample_id,
        tags=["application-sdk"],
        metadata={
            "operation": event.operation,
            "permissions": list(event.permissions),
            "correlation_id": event.correlation_id,
        },
    )
    if identity is None:
        raise api_error(503, "Application access audit is unavailable", category="setup")


def ingest_submission_services() -> "IngestSubmissionServices":
    """Bind durable ingestion acceptance and allowlisted worker publication ports."""
    from api.app.deps.repositories import get_ingest_jobs_repository
    from api.config.runtime_settings import DefaultConfig
    from coyote3.application.operations.ingest import IngestSubmissionServices

    return IngestSubmissionServices(
        jobs=get_ingest_jobs_repository,
        publish=publish_ingest_job,
        queue=DefaultConfig.CELERY_INGEST_QUEUE,
    )


def publish_ingest_job(kind: str, identity: str) -> None:
    """Notify the worker for an already retained ingestion job.

    Args:
        kind: Supported durable ingestion job kind.
        identity: Identifier of the accepted durable job; reused as the delivery ID.
    """
    from api.config.runtime_settings import DefaultConfig
    from api.tasks.ingest import (
        ingest_sample_bundle_task,
        insert_collection_document_task,
        insert_collection_documents_task,
        upsert_collection_document_task,
    )

    tasks = {
        "sample_bundle": ingest_sample_bundle_task,
        "insert_document": insert_collection_document_task,
        "insert_documents": insert_collection_documents_task,
        "upsert_document": upsert_collection_document_task,
    }
    tasks[kind].apply_async(
        kwargs={"job_id": identity}, task_id=identity, queue=DefaultConfig.CELERY_INGEST_QUEUE
    )


def open_sample_ingestion(
    authenticate: Callable[[], Any], *, correlation_id: str | None = None
) -> "Ingestion":
    """Bind a verified, expiring machine credential to synchronous sample ingestion only.

    Args:
        authenticate: Trusted transport verifier rerun before every operation.
        correlation_id: Host correlation identifier; None allocates one per operation.

    Returns:
        Ingestion operations whose runtime rejects collection writes and asynchronous jobs.
    """
    from api.app.deps.services import get_internal_ingest_service
    from api.infra.mongo.records import application_result
    from api.infra.security.ingest_policy import SampleIngestPolicy
    from api.security.access import InternalIngestPrincipal
    from coyote3.application.operations.ingest import Ingestion

    runtime = ApplicationRuntime(
        authenticate=authenticate,
        policy_factory=lambda actor: SampleIngestPolicy(InternalIngestPrincipal),
        sample_loader=lambda identity: None,
        assay_loader=lambda identity: None,
        audit_access=record_application_access,
        correlation_id=correlation_id,
        project_result=application_result,
        allowed_operations=frozenset(
            {
                "ingest.sample_bundle",
                "ingest.parse_yaml",
                "ingest.authorize_sample",
                "ingest.prepare_upload",
                "ingest.manifest",
            }
        ),
    )
    return Ingestion(runtime, get_internal_ingest_service, ingest_submission_services())


def internal_reference_services() -> "InternalReferenceServices":
    """Bind only role-level and gene-list identity metadata for ingestion tooling."""
    from coyote3.application.operations.internal_references import InternalReferenceServices

    return InternalReferenceServices(
        role_levels=internal_role_levels, gene_list_metadata=internal_gene_list_metadata
    )


def internal_role_levels() -> dict[str, int]:
    """Read registered role levels through the configured identity repository."""
    from api.app.deps.repositories import get_roles_repository

    return {
        str(role["role_id"]): int(role.get("level", 0))
        for role in get_roles_repository().get_all_roles() or []
        if role.get("role_id")
    }


def internal_gene_list_metadata(identifier: str) -> dict[str, Any]:
    """Read the established ingestion metadata fields through the configured repository.

    Args:
        identifier: Registered gene-list identifier.

    Returns:
        Ad-hoc flag and display name, excluding list contents and persistence metadata.
    """
    from api.app.deps.repositories import get_gene_list_repository

    repository = get_gene_list_repository()
    return {
        "is_adhoc": bool(repository.is_isgl_adhoc(identifier)),
        "display_name": repository.get_isgl_display_name(identifier),
    }


def open_internal_references(
    authenticate: Callable[[], Any], *, correlation_id: str | None = None
) -> "InternalReferences":
    """Bind trusted-token tooling to its two established reference metadata operations.

    Args:
        authenticate: Trusted static-token verifier rerun before each read.
        correlation_id: Host correlation identifier; None allocates one per operation.

    Returns:
        Restricted reference operations with current verification and durable access audit.
    """
    from api.infra.mongo.records import application_result
    from api.infra.security.ingest_policy import SampleIngestPolicy
    from api.security.access import InternalIngestPrincipal
    from coyote3.application.operations.internal_references import InternalReferences

    runtime = ApplicationRuntime(
        authenticate=authenticate,
        policy_factory=lambda actor: SampleIngestPolicy(InternalIngestPrincipal),
        sample_loader=lambda identity: None,
        assay_loader=lambda identity: None,
        audit_access=record_application_access,
        correlation_id=correlation_id,
        project_result=application_result,
        allowed_operations=frozenset(
            {"internal_references.role_levels", "internal_references.gene_list_metadata"}
        ),
    )
    return InternalReferences(runtime, internal_reference_services())


def change_account_password(
    *, user_id: str, current_password: str, new_password: str
) -> dict[str, Any]:
    """Replace a verified account's local credential through the identity adapter.

    Args:
        user_id: Current verified username.
        current_password: Credential to verify before replacement.
        new_password: Proposed password after application complexity validation.

    Returns:
        Identity-adapter outcome after replacement and session invalidation.
    """
    from api.security.password_flows import change_local_password

    return dict(
        change_local_password(
            user_id=user_id, current_password=current_password, new_password=new_password
        )
    )


def open_password_recovery() -> "PasswordRecovery":
    """Bind only one-time recovery delivery and atomic credential consumption."""
    from api.security.password_flows import (
        consume_password_token_and_set_password,
        issue_password_token_for_user,
    )
    from coyote3.application.operations.account import PasswordRecovery

    return PasswordRecovery(
        request_token=issue_password_token_for_user,
        consume_token=consume_password_token_and_set_password,
    )


def maintenance_executor(logger: Any) -> "MaintenanceExecution":
    """Compose restricted background workflows without granting interactive administration.

    Args:
        logger: Host operational logger used for execution decisions and scope refresh failures.

    Returns:
        Fixed maintenance capability; task scheduling, gating and process locks remain host-owned.
    """
    from api.app.deps.services import (
        get_activity_notification_service,
        get_app_controls_service,
        get_audit_service,
        get_dashboard_service,
        get_notification_service,
        get_public_oncokb_refresh_service,
    )
    from api.infra.security.maintenance_policy import (
        MaintenanceWorkerIdentity,
        MaintenanceWorkerPolicy,
    )
    from api.security.access import api_user_from_user_doc
    from coyote3.application.operations.maintenance import MaintenanceExecution, MaintenanceServices

    def audit(event: AccessEvent) -> None:
        """Record worker access without making audit recovery depend on an unavailable queue."""
        logger.info(
            "application_worker_access operation=%s allowed=%s worker=celery-maintenance correlation_id=%s",
            event.operation,
            event.allowed,
            event.correlation_id,
        )

    def replay() -> int:
        """Replay pending audit delivery when the existing delivery service is available."""
        service = get_audit_service()
        return int(service.replay_pending()) if service is not None else 0

    runtime = ApplicationRuntime(
        authenticate=MaintenanceWorkerIdentity,
        policy_factory=lambda actor: MaintenanceWorkerPolicy(),
        sample_loader=lambda identity: None,
        assay_loader=lambda identity: None,
        audit_access=audit,
        allowed_operations=frozenset(
            {
                "maintenance.erase_reports",
                "maintenance.finalize_reports",
                "maintenance.replay_audit",
                "maintenance.deliver_emails",
                "maintenance.retention",
                "maintenance.refresh_public_oncokb",
                "maintenance.refresh_dashboard",
            }
        ),
    )
    services = MaintenanceServices(
        erase_reports=erase_committed_report_files,
        finalize_reports=finalize_committed_report_files,
        replay_audit=replay,
        deliver_activity=lambda: get_activity_notification_service().deliver(),
        deliver_emails=lambda: dict(get_notification_service().deliver_emails(limit=10)),
        retention=lambda: dict(get_app_controls_service().run_maintenance()),
        oncokb=lambda: dict(get_public_oncokb_refresh_service().refresh()),
        dashboard=get_dashboard_service,
        users=lambda: list(get_dashboard_service().user_repository.get_all_users()),
        identity=api_user_from_user_doc,
        logger=logger,
    )
    return MaintenanceExecution(runtime, services)


def erase_committed_report_files() -> dict[str, int]:
    """Erase only files queued by committed sample deletions through the storage adapter."""
    from api.app.container import store
    from api.config.paths import REPORTS_BASE_PATH
    from api.infra.mongo.repositories.report_artifact_erasure import erase_pending_reports

    repository = store.report_repository
    return dict(
        erase_pending_reports(
            repository.get_collection(),
            root=repository.app.config.get("REPORTS_BASE_PATH", REPORTS_BASE_PATH),
        )
    )


def finalize_committed_report_files() -> dict[str, int]:
    """Resume checksum-verified publication for committed report artifacts."""
    from api.app.container import store
    from api.config.paths import REPORTS_BASE_PATH
    from coyote3.application.reporting.artifact_finalization import finalize_pending_reports

    repository = store.report_repository
    return dict(
        finalize_pending_reports(
            repository, root=repository.app.config.get("REPORTS_BASE_PATH", REPORTS_BASE_PATH)
        )
    )
