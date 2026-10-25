"""HTTP composition for the authenticated in-process application SDK."""

from typing import Any

from fastapi import Depends, Request

from api.app.application_factory import (
    open_application,
    open_authenticated_runtime,
    open_public_application,
    open_sample_ingestion,
)
from api.security.access import get_request_api_session, require_sample_ingest_access
from api.services.installation import Installation
from api.services.public_pages import PublicPages
from coyote3.application.common.execution_context import current_request_id
from coyote3.application.operations import (
    ClinicalRules,
    ConfigurationProfiles,
    ConfigurationPromotions,
    CoyoteApplication,
    QueryRules,
)
from coyote3.application.operations.account import Account, PasswordRecovery
from coyote3.application.operations.administration import (
    AssayConfigurations,
    AssayGroups,
    Assays,
    AssaySetups,
    CatalogAuthoring,
    Diagnoses,
    GeneLists,
    Permissions,
    ReferenceData,
    Roles,
    SampleAdministration,
    Users,
)
from coyote3.application.operations.clinical import Findings, SmallVariants
from coyote3.application.operations.coverage import Coverage
from coyote3.application.operations.ingest import Ingestion
from coyote3.application.operations.internal_references import InternalReferences
from coyote3.application.operations.knowledgebase import Knowledgebase
from coyote3.application.operations.notifications import Notifications
from coyote3.application.operations.public import PublicApplication
from coyote3.application.operations.samples import Sample, Samples
from coyote3.application.operations.system import (
    Controls,
    Credentials,
    Dashboard,
    Traceability,
)


def get_application(request: Request) -> CoyoteApplication:
    """Bind local SDK operations to the request's verified, revocable session.

    Args:
        request: Authenticated HTTP request; authentication remains an HTTP responsibility.

    Returns:
        Application resources that recheck current identity and grants before execution.
    """
    session = get_request_api_session(request)
    return open_application(session.token, correlation_id=current_request_id())


def get_public_pages() -> PublicPages:
    """Compose public product pages using host configuration and SDK reference reads."""
    from api.app.runtime_state import app

    return PublicPages(app.config, open_public_application())


def get_query_rules(application: CoyoteApplication = Depends(get_application)) -> QueryRules:
    """Inject the same authorized query-policy operations used by local Python callers."""
    return application.query_rules


def get_clinical_rules(application: CoyoteApplication = Depends(get_application)) -> ClinicalRules:
    """Inject the same authorized reporting-rule operations used by local Python callers."""
    return application.clinical_rules


def get_configuration_profiles(
    application: CoyoteApplication = Depends(get_application),
) -> ConfigurationProfiles:
    """Inject the shared configuration source-profile authoring operations."""
    return application.configuration_profiles


def get_configuration_promotions(
    application: CoyoteApplication = Depends(get_application),
) -> ConfigurationPromotions:
    """Inject the shared reviewed environment-promotion operations."""
    return application.configuration_promotions


def get_small_variants(
    sample_id: str,
    application: CoyoteApplication = Depends(get_application),
) -> SmallVariants:
    """Inject authorized small-variant operations bound to the requested sample identifier."""
    return application.samples.ref(sample_id).variants


def get_cnvs(
    sample_id: str,
    application: CoyoteApplication = Depends(get_application),
) -> Findings:
    """Inject authorized copy-number operations bound to the requested sample identifier."""
    return application.samples.ref(sample_id).cnvs


def get_translocations(
    sample_id: str,
    application: CoyoteApplication = Depends(get_application),
) -> Findings:
    """Inject authorized translocation operations bound to the requested sample identifier."""
    return application.samples.ref(sample_id).translocations


def get_fusions(
    sample_id: str,
    application: CoyoteApplication = Depends(get_application),
) -> Findings:
    """Inject authorized fusion operations bound to the requested sample identifier."""
    return application.samples.ref(sample_id).fusions


def get_sample(
    sample_id: str,
    application: CoyoteApplication = Depends(get_application),
) -> Sample:
    """Inject authorized sample operations without accepting caller-supplied scope attributes."""
    return application.samples.ref(sample_id)


def get_named_sample(
    sample_name: str,
    application: CoyoteApplication = Depends(get_application),
) -> Sample:
    """Bind the named-sample HTTP route to the same authorized sample operations."""
    return application.samples.ref(sample_name)


def get_coverage(application: CoyoteApplication = Depends(get_application)) -> Coverage:
    """Inject the shared coverage blacklist read and curation operations."""
    return application.coverage


def get_samples(application: CoyoteApplication = Depends(get_application)) -> Samples:
    """Inject current-session sample catalog and navigation operations."""
    return application.samples


def get_users(application: CoyoteApplication = Depends(get_application)) -> Users:
    """Inject the shared authorized users operations."""
    return application.users


def get_roles(application: CoyoteApplication = Depends(get_application)) -> Roles:
    """Inject the shared authorized roles operations."""
    return application.roles


def get_permissions(application: CoyoteApplication = Depends(get_application)) -> Permissions:
    """Inject the shared authorized permissions operations."""
    return application.permissions


def get_assays(application: CoyoteApplication = Depends(get_application)) -> Assays:
    """Inject the shared authorized assays operations."""
    return application.assays


def get_assay_groups(application: CoyoteApplication = Depends(get_application)) -> AssayGroups:
    """Inject the shared authorized assay groups operations."""
    return application.assay_groups


def get_diagnoses(application: CoyoteApplication = Depends(get_application)) -> Diagnoses:
    """Inject the shared authorized diagnoses operations."""
    return application.diagnoses


def get_assay_configurations(
    application: CoyoteApplication = Depends(get_application),
) -> AssayConfigurations:
    """Inject the shared authorized assay configurations operations."""
    return application.assay_configurations


def get_gene_lists(application: CoyoteApplication = Depends(get_application)) -> GeneLists:
    """Inject the shared authorized gene lists operations."""
    return application.gene_lists


def get_sample_administration(
    application: CoyoteApplication = Depends(get_application),
) -> SampleAdministration:
    """Inject the shared authorized sample administration operations."""
    return application.sample_administration


def get_assay_setups(application: CoyoteApplication = Depends(get_application)) -> AssaySetups:
    """Inject the shared authorized assay setups operations."""
    return application.assay_setups


def get_catalog_authoring(
    application: CoyoteApplication = Depends(get_application),
) -> CatalogAuthoring:
    """Inject the shared authorized catalog authoring operations."""
    return application.catalog_authoring


def get_reference_data(application: CoyoteApplication = Depends(get_application)) -> ReferenceData:
    """Inject the shared authorized reference data operations."""
    return application.reference_data


def get_knowledgebase(application: CoyoteApplication = Depends(get_application)) -> Knowledgebase:
    """Inject the shared knowledgebase application operations."""
    return application.knowledgebase


def get_notifications(application: CoyoteApplication = Depends(get_application)) -> Notifications:
    """Inject the shared notifications application operations."""
    return application.notifications


def get_dashboard(application: CoyoteApplication = Depends(get_application)) -> Dashboard:
    """Inject the shared dashboard application operations."""
    return application.dashboard


def get_controls(application: CoyoteApplication = Depends(get_application)) -> Controls:
    """Inject the shared controls application operations."""
    return application.controls


def get_installation(request: Request) -> Installation:
    """Bind host installation workflows to current session permissions and access auditing."""
    from api.app.deps.services import get_demo_installation_service, get_deployment_data_service
    from api.services.installation import InstallationServices

    session = get_request_api_session(request)
    return Installation(
        open_authenticated_runtime(session.token, correlation_id=current_request_id()),
        InstallationServices(
            demo=get_demo_installation_service, deployment=get_deployment_data_service
        ),
    )


def get_traceability(application: CoyoteApplication = Depends(get_application)) -> Traceability:
    """Inject the shared traceability application operations."""
    return application.traceability


def get_credentials(application: CoyoteApplication = Depends(get_application)) -> Credentials:
    """Inject the shared credentials application operations."""
    return application.credentials


def get_public_application() -> PublicApplication:
    """Inject anonymous published-catalog reads without constructing clinical access."""
    return open_public_application()


def get_ingestion(application: CoyoteApplication = Depends(get_application)) -> Ingestion:
    """Inject current-session synchronous and asynchronous ingestion operations."""
    return application.ingest


def get_sample_ingestion(request: Request) -> Ingestion:
    """Bind synchronous ingestion to a current session or the restricted machine audience."""
    if not ({"x-coyote-ingest-token", "x-coyote-internal-token"} & set(request.headers)):
        return get_application(request).ingest

    def authenticate() -> Any:
        """Reverify signature, expiry and environment before each SDK operation."""
        verifier = require_sample_ingest_access(request)
        try:
            return next(verifier)
        finally:
            verifier.close()

    return open_sample_ingestion(authenticate, correlation_id=current_request_id())


def get_internal_references(request: Request) -> InternalReferences:
    """Bind static-token tooling to allowlisted metadata reads, with no collection writes."""
    from api.app.application_factory import open_internal_references
    from api.security.access import _require_internal_token

    def authenticate() -> Any:
        """Recheck the static internal token and deployment identity for every read."""
        _require_internal_token(request)
        verifier = require_sample_ingest_access(request)
        try:
            return next(verifier)
        finally:
            verifier.close()

    return open_internal_references(authenticate, correlation_id=current_request_id())


def get_account(application: CoyoteApplication = Depends(get_application)) -> Account:
    """Inject operations bound only to the current verified account."""
    return application.account


def get_password_recovery() -> PasswordRecovery:
    """Inject one-time credential recovery without granting account or clinical reads."""
    from api.app.application_factory import open_password_recovery

    return open_password_recovery()
