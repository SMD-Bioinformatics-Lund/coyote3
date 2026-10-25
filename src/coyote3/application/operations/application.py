"""Explicit composition of the supported local application resources."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from coyote3.application.operations.account import Account, PasswordRecovery
from coyote3.application.operations.administration import (
    AdministrationServices,
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
from coyote3.application.operations.clinical import ClinicalServices
from coyote3.application.operations.clinical_rules import ClinicalRules
from coyote3.application.operations.coverage import Coverage
from coyote3.application.operations.editing import DocumentEditors, EditableResource
from coyote3.application.operations.governance import (
    ConfigurationProfiles,
    ConfigurationPromotions,
    QueryRules,
)
from coyote3.application.operations.ingest import Ingestion, IngestSubmissionServices
from coyote3.application.operations.internal_references import (
    InternalReferences,
    InternalReferenceServices,
)
from coyote3.application.operations.knowledgebase import Knowledgebase
from coyote3.application.operations.notifications import Notifications
from coyote3.application.operations.public import PublicApplication
from coyote3.application.operations.reporting import ReportingServices, Reports
from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.application.operations.samples import Samples
from coyote3.application.operations.system import (
    Controls,
    Credentials,
    Dashboard,
    OperationsServices,
    Traceability,
)
from coyote3.config.contracts.application import APP_CONTROLS_ID

if TYPE_CHECKING:
    from coyote3.application.common.query_service import CommonQueryService
    from coyote3.application.ingest.service import InternalIngestService
    from coyote3.application.notifications.service import NotificationService
    from coyote3.application.query_rules.service import QueryRuleService
    from coyote3.application.query_rules.testing import QueryRuleTestingService
    from coyote3.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
    from coyote3.application.reporting.clinical_rules.testing import ClinicalRuleTestingService
    from coyote3.application.resources.configuration_profiles import ConfigurationProfileService
    from coyote3.application.resources.configuration_promotions import ConfigurationPromotionService


class ApplicationServices:
    """Host-owned factories; creating an SDK does not eagerly connect its dependencies."""

    def __init__(
        self,
        *,
        clinical: ClinicalServices,
        administration: AdministrationServices,
        operations: OperationsServices,
        public: Callable[[], PublicApplication],
        change_password: Callable[..., dict[str, object]],
        password_recovery: Callable[[], PasswordRecovery],
        knowledgebase: Callable[[], CommonQueryService],
        knowledgebase_search_limit: int,
        notifications: Callable[[], NotificationService],
        reporting: ReportingServices,
        ingest: Callable[[], InternalIngestService],
        ingest_submission: IngestSubmissionServices,
        internal_references: InternalReferenceServices,
        query_rules: Callable[[], QueryRuleService],
        configuration_profiles: Callable[[], ConfigurationProfileService],
        configuration_promotions: Callable[[], ConfigurationPromotionService],
        clinical_rules: Callable[[], ClinicalRuleAuthoringService],
        query_rule_testing: Callable[[], QueryRuleTestingService],
        clinical_rule_testing: Callable[[], ClinicalRuleTestingService],
    ) -> None:
        """Bind operation implementations without opening their repositories.

        Args:
            clinical: Finding, sample, classification and registered-artifact capabilities.
            administration: Account, assay and managed-resource implementation factories.
            operations: Dashboard, controls, installation and operational task ports.
            public: Constructs the restricted anonymous published-data capability.
            change_password: Verifies and replaces a current account's local credential.
            password_recovery: Constructs one-time recovery with verified token consumption.
            knowledgebase: Local reference evidence and access-scoped cohort workflows.
            knowledgebase_search_limit: Default maximum tiered-search entries from host settings.
            notifications: Recipient and broadcast delivery workflows.
            reporting: Clinical report preparation, rendering, persistence and artifact ports.
            ingest: Existing validated transactional ingestion implementation.
            ingest_submission: Durable acceptance, worker publication and status ports.
            internal_references: Allowlisted metadata lookups for trusted ingestion tooling.
            query_rules: Query-policy authoring and lifecycle implementation.
            configuration_profiles: Source-profile authoring and publication implementation.
            configuration_promotions: Reviewed environment-release promotion implementation.
            clinical_rules: Clinical reporting-rule authoring and lifecycle implementation.
            query_rule_testing: Read-only policy comparisons and scoped testing samples.
            clinical_rule_testing: Read-only report-rule comparisons and scoped testing samples.
        """
        self.clinical, self.reporting = clinical, reporting
        self.administration = administration
        self.operations, self.knowledgebase = operations, knowledgebase
        self.public = public
        self.change_password, self.password_recovery = change_password, password_recovery
        self.knowledgebase_search_limit = knowledgebase_search_limit
        self.notifications = notifications
        self.ingest, self.query_rules = ingest, query_rules
        self.ingest_submission = ingest_submission
        self.internal_references = internal_references
        self.clinical_rules = clinical_rules
        self.query_rule_testing, self.clinical_rule_testing = (
            query_rule_testing,
            clinical_rule_testing,
        )
        self.configuration_profiles, self.configuration_promotions = (
            configuration_profiles,
            configuration_promotions,
        )


class CoyoteApplication:
    """Authenticated local resources composed over the existing application services.

    The runtime and factories are trusted host capabilities, not request data.
    An SDK instance may be retained, but no authorization decision is retained
    between calls. Only the documented resources form the supported Python surface.
    """

    def __init__(self, runtime: ApplicationRuntime, services: ApplicationServices) -> None:
        """Bind application resources without starting a web server or opening storage.

        Args:
            runtime: Authentication, current-policy, scope and access-audit capabilities.
            services: Lazy use-case services and explicit reporting dependencies.
        """
        self.samples = Samples(runtime, services.clinical)
        self.public = services.public()
        self.account = Account(runtime, services.administration.users, services.change_password)
        self.password_recovery = services.password_recovery()
        self.internal_references = InternalReferences(runtime, services.internal_references)
        self.knowledgebase = Knowledgebase(
            runtime, services.knowledgebase, search_limit=services.knowledgebase_search_limit
        )
        self.notifications = Notifications(runtime, services.notifications)
        self.dashboard = Dashboard(runtime, services.operations)
        self.controls = Controls(runtime, services.operations)
        self.traceability = Traceability(runtime, services.operations)
        self.credentials = Credentials(runtime, services.operations)
        self.users = Users(runtime, services.administration.users)
        self.roles = Roles(runtime, services.administration.roles)
        self.permissions = Permissions(runtime, services.administration.permissions)
        self.assays = Assays(runtime, services.administration.assays)
        self.assay_groups = AssayGroups(runtime, services.administration.assay_groups)
        self.diagnoses = Diagnoses(runtime, services.administration.diagnoses)
        self.assay_configurations = AssayConfigurations(
            runtime, services.administration.assay_configurations
        )
        self.gene_lists = GeneLists(runtime, services.administration.gene_lists)
        self.sample_administration = SampleAdministration(
            runtime, services.administration.sample_administration
        )
        self.assay_setups = AssaySetups(runtime, services.administration.assay_setups)
        self.catalog_authoring = CatalogAuthoring(
            runtime, services.administration.catalog_authoring
        )
        self.reference_data = ReferenceData(runtime, services.administration.reference_data)
        self.coverage = Coverage(runtime, services.clinical)
        self.reports = Reports(runtime, services.reporting)
        self.ingest = Ingestion(runtime, services.ingest, services.ingest_submission)
        self.query_rules = QueryRules(runtime, services.query_rules, services.query_rule_testing)
        self.clinical_rules = ClinicalRules(
            runtime, services.clinical_rules, services.clinical_rule_testing
        )
        self.configuration_profiles = ConfigurationProfiles(
            runtime, services.configuration_profiles
        )
        self.configuration_promotions = ConfigurationPromotions(
            runtime, services.configuration_promotions
        )
        administration = services.administration
        self.editing = DocumentEditors(
            runtime,
            {
                "sample-filters": EditableResource(
                    "sample:edit:own",
                    lambda identity: runtime.sample_loader(identity) or {},
                    "_id",
                    sample_scoped=True,
                ),
                "diagnoses": EditableResource(
                    "assay.panel:edit",
                    lambda identity: administration.diagnoses().get_definition(identity),
                    "diagnosis_id",
                ),
                "controls": EditableResource(
                    "app.controls:edit",
                    lambda identity: (
                        {"_id": APP_CONTROLS_ID} if identity == APP_CONTROLS_ID else {}
                    ),
                    "_id",
                ),
                "samples": EditableResource(
                    "sample:edit:global",
                    lambda identity: administration.sample_administration().context_payload(
                        sample_id=identity
                    )["sample"],
                    "_id",
                ),
                "users": EditableResource(
                    "user:edit",
                    lambda identity: administration.users().context_payload(user_id=identity)[
                        "user_doc"
                    ],
                    "username",
                ),
                "roles": EditableResource(
                    "role:edit",
                    lambda identity: administration.roles().context_payload(role_id=identity)[
                        "role"
                    ],
                    "role_id",
                ),
                "permissions": EditableResource(
                    "permission.policy:edit",
                    lambda identity: administration.permissions().context_payload(
                        permission_id=identity
                    )["permission"],
                    "permission_id",
                ),
                "asp": EditableResource(
                    "assay.panel:edit",
                    lambda identity: administration.assays().context_payload(panel_id=identity)[
                        "panel"
                    ],
                    "asp_id",
                ),
                "aspc": EditableResource(
                    "assay.config:edit",
                    lambda identity: administration.assay_configurations().context_payload(
                        assay_id=identity
                    )["assay_config"],
                    "aspc_id",
                ),
                "genelists": EditableResource(
                    "gene_list.insilico:edit",
                    lambda identity: administration.gene_lists().context_payload(
                        genelist_id=identity
                    )["genelist"],
                    "isgl_id",
                ),
                "assay-setups": EditableResource(
                    "assay.panel:edit",
                    lambda identity: administration.assay_setups().get(identity),
                    "_id",
                ),
                "clinical-rules": EditableResource(
                    "clinical_rules:draft",
                    lambda identity: services.clinical_rules().get(identity),
                    "_id",
                ),
                "query-rules": EditableResource(
                    "query_rules:draft",
                    lambda identity: services.query_rules().get(identity),
                    "_id",
                ),
                "assay-catalog": EditableResource(
                    "catalog:draft",
                    lambda identity: administration.catalog_authoring().document(identity),
                    "_id",
                ),
            },
        )
        runtime.edit_guard = self.editing.require_owner
