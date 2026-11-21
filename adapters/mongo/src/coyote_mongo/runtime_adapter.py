# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""MongoDB connections, collection bindings and repository composition."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pymongo.errors import OperationFailure

from coyote_mongo.config.settings import AuditContext, MongoSettings
from coyote_mongo.connections import MongoConnections
from coyote_mongo.knowledgebase.clinpgx_public import ClinPgxPublicRepository
from coyote_mongo.knowledgebase.oncokb_public_cache import OncoKbPublicCacheRepository
from coyote_mongo.knowledgebase.plugins import BUILTIN_KNOWLEDGEBASE_REPOSITORIES
from coyote_mongo.repositories.anno_vep import AnnoVepRepository
from coyote_mongo.repositories.annotations import AnnotationsRepository
from coyote_mongo.repositories.assay_configurations import ASPConfigRepository
from coyote_mongo.repositories.assay_diagnoses import AssayDiagnosisRepository
from coyote_mongo.repositories.assay_groups import AssayGroupRepository
from coyote_mongo.repositories.assay_panels import ASPRepository
from coyote_mongo.repositories.assay_setup import (
    AssaySetupRepository,
    AssaySetupRevisionRepository,
)
from coyote_mongo.repositories.bam_records import BamServiceRepository
from coyote_mongo.repositories.biomarkers import BiomarkerRepository
from coyote_mongo.repositories.blacklist import BlacklistRepository
from coyote_mongo.repositories.clinical_rule_sets import (
    ClinicalRuleRevisionRepository,
    ClinicalRuleSetRepository,
)
from coyote_mongo.repositories.configuration_profiles import ConfigurationProfileRepository
from coyote_mongo.repositories.copy_number_variants import CNVsRepository
from coyote_mongo.repositories.coverage import CoverageRepository
from coyote_mongo.repositories.d4_coverage import D4CoverageRepository
from coyote_mongo.repositories.d4_coverage_blacklist import D4CoverageBlacklistRepository
from coyote_mongo.repositories.edit_leases import MongoEditLeaseRepository
from coyote_mongo.repositories.expression import ExpressionRepository
from coyote_mongo.repositories.finding_comments import FindingCommentsRepository
from coyote_mongo.repositories.fusions import FusionsRepository
from coyote_mongo.repositories.gene_lists import ISGLRepository
from coyote_mongo.repositories.ingest_jobs import IngestJobsRepository
from coyote_mongo.repositories.notifications import NotificationsRepository
from coyote_mongo.repositories.permissions import PermissionsRepository
from coyote_mongo.repositories.pgx import PgxRepository
from coyote_mongo.repositories.public_assay_catalog import PublicAssayCatalogRepository
from coyote_mongo.repositories.public_assay_catalog_versions import (
    PublicAssayCatalogRevisionRepository,
    PublicAssayCatalogVersionRepository,
)
from coyote_mongo.repositories.query_rule_revisions import QueryRuleRevisionRepository
from coyote_mongo.repositories.query_rules import QueryRuleRepository
from coyote_mongo.repositories.reported_variants import ReportedVariantsRepository
from coyote_mongo.repositories.reports import ReportRepository
from coyote_mongo.repositories.rna_classification import RNAClassificationRepository
from coyote_mongo.repositories.rna_expression import RNAExpressionRepository
from coyote_mongo.repositories.rna_quality import RNAQCRepository
from coyote_mongo.repositories.roles import RolesRepository
from coyote_mongo.repositories.sample_comments import SampleCommentsRepository
from coyote_mongo.repositories.samples import SampleRepository
from coyote_mongo.repositories.translocations import TranslocsRepository
from coyote_mongo.repositories.users import UsersRepository
from coyote_mongo.repositories.variants import VariantsRepository
from coyote_mongo.repositories.vep_metadata import VEPMetaRepository

CORE_REPOSITORIES: tuple[tuple[str, type[Any], str], ...] = (
    ("edit_lease_repository", MongoEditLeaseRepository, "edit_leases"),
    ("configuration_profile_repository", ConfigurationProfileRepository, "configuration_profiles"),
    ("translocation_repository", TranslocsRepository, "translocs"),
    ("copy_number_variant_repository", CNVsRepository, "cnvs"),
    ("variant_repository", VariantsRepository, "variants"),
    ("anno_vep_repository", AnnoVepRepository, "anno_vep"),
    ("annotation_repository", AnnotationsRepository, "annotations"),
    ("sample_repository", SampleRepository, "samples"),
    ("ingest_jobs_repository", IngestJobsRepository, "ingest_jobs"),
    ("sample_comment_repository", SampleCommentsRepository, "sample_comments"),
    ("finding_comment_repository", FindingCommentsRepository, "finding_comments"),
    ("assay_panel_repository", ASPRepository, "asp"),
    ("assay_diagnosis_repository", AssayDiagnosisRepository, "assay_diagnoses"),
    ("assay_setup_repository", AssaySetupRepository, "assay_setups"),
    ("assay_group_repository", AssayGroupRepository, "assay_groups"),
    ("assay_setup_revision_repository", AssaySetupRevisionRepository, "assay_setup_revisions"),
    ("blacklist_repository", BlacklistRepository, "blacklist"),
    ("expression_repository", ExpressionRepository, "expression"),
    ("bam_record_repository", BamServiceRepository, "bam_service"),
    ("user_repository", UsersRepository, "users"),
    ("fusion_repository", FusionsRepository, "fusions"),
    ("biomarker_repository", BiomarkerRepository, "biomarkers"),
    ("pgx_repository", PgxRepository, "pgx"),
    ("d4_coverage_repository", D4CoverageRepository, "d4_coverage"),
    ("coverage_repository", CoverageRepository, "coverage"),
    ("d4_coverage_blacklist_repository", D4CoverageBlacklistRepository, "d4_coverage_blacklist"),
    ("assay_configuration_repository", ASPConfigRepository, "aspc"),
    ("roles_repository", RolesRepository, "roles"),
    ("permissions_repository", PermissionsRepository, "permissions"),
    ("notification_repository", NotificationsRepository, "notifications"),
    ("vep_metadata_repository", VEPMetaRepository, "vep_meta"),
    ("gene_list_repository", ISGLRepository, "isgl"),
    ("rna_expression_repository", RNAExpressionRepository, "rna_expression"),
    ("rna_classification_repository", RNAClassificationRepository, "rna_classification"),
    ("rna_quality_repository", RNAQCRepository, "rna_qc"),
    ("reported_variant_repository", ReportedVariantsRepository, "reported_variants"),
    ("report_repository", ReportRepository, "reports"),
    ("clinical_rule_set_repository", ClinicalRuleSetRepository, "clinical_rule_sets"),
    ("query_rule_repository", QueryRuleRepository, "query_rule_sets"),
    ("query_rule_revision_repository", QueryRuleRevisionRepository, "query_rule_revisions"),
    (
        "clinical_rule_revision_repository",
        ClinicalRuleRevisionRepository,
        "clinical_rule_revisions",
    ),
    ("public_assay_catalog_repository", PublicAssayCatalogRepository, "public_assay_catalog"),
    (
        "public_assay_catalog_revision_repository",
        PublicAssayCatalogRevisionRepository,
        "public_assay_catalog_revisions",
    ),
    (
        "public_assay_catalog_version_repository",
        PublicAssayCatalogVersionRepository,
        "public_assay_catalog_versions",
    ),
    ("oncokb_public_cache_repository", OncoKbPublicCacheRepository, "oncokb_public_cache"),
    ("clinpgx_public_repository", ClinPgxPublicRepository, "clinpgx_public"),
)


@dataclass
class MongoRuntime:
    """Adapter-owned settings and host services, without retaining the API runtime."""

    config: dict[str, Any] = field(repr=False)
    logger: logging.Logger
    audit: AuditContext
    cache: Any | None = field(default=None, repr=False)


class MongoAdapter:
    """Own persistence connections and repositories for an explicitly configured host."""

    ingest_jobs_repository: IngestJobsRepository
    user_repository: UsersRepository
    report_repository: ReportRepository
    reported_variant_repository: ReportedVariantsRepository

    def __init__(self, *, operation_observer: Callable[..., None] | None = None) -> None:
        """Initialize without opening database connections.

        Args:
            operation_observer: Optional host callback receiving operation, outcome
                and duration_ms keyword arguments for index-setup observations.
                None disables metric delivery without importing a metrics host.
        """
        self.client = None
        self._connections = None
        self._operation_observer = operation_observer

    def observe_operation(self, **event: Any) -> None:
        """Forward an index-operation metric when the consuming host supplies an observer."""
        if self._operation_observer is not None:
            self._operation_observer(**event)

    def connect(
        self, settings: MongoSettings, *, logger: logging.Logger | None = None, cache: Any = None
    ):
        """Bind logical databases using validated adapter-owned deployment inputs.

        Args:
            settings: Persistence settings selected explicitly by the consuming host.
            logger: Optional host logger; otherwise use the adapter's logger.
            cache: Optional cache port used by sample queries.
        """
        if not isinstance(settings, MongoSettings):
            raise TypeError("MongoAdapter requires MongoSettings, not an application context")
        self.settings = settings
        self.app = MongoRuntime(
            settings.runtime_values(), logger or logging.getLogger(__name__), settings.audit, cache
        )
        self._connections = MongoConnections(self.app.config)
        self.coyote_db = self._connections.databases["primary"]
        self.identity_db = self._connections.databases["identity"]
        self.knowledgebase_db = self._connections.databases["knowledgebase"]
        self.bam_db = self._connections.databases["bam"]
        # Existing app-owned transactions use the primary client only.
        self.client = self.coyote_db.client

    def close(self):
        """Close owned MongoDB clients if connections have been initialized."""
        if self._connections is not None:
            self._connections.close()

    def ping(self):
        """Ping initialized connections, propagating connection failures."""
        self._connections.ping()

    def initialize(
        self, settings: MongoSettings, *, logger: logging.Logger | None = None, cache: Any = None
    ) -> None:
        """Initialize repositories without importing or retaining a host application.

        Args:
            settings: Validated connection, collection and audit settings.
            logger: Optional logger for persistence diagnostics.
            cache: Optional sample-query cache port.
        """
        try:
            self.connect(settings, logger=logger, cache=cache)
            self.setup()
            self._setup_repositories(ensure_indexes=False)
            self.verify_index_contracts()
        except Exception:
            self.close()
            raise

    def get_db_name(self) -> str:
        """Read the configured primary application database name.

        Returns:
            The runtime's ``COYOTE4_DB`` setting.

        Raises:
            KeyError: If the connected runtime has no ``COYOTE4_DB`` setting.
        """
        return self.app.config["COYOTE4_DB"]

    def setup(self) -> None:
        """Bind configured collections by logical ownership, not physical DB name."""
        for service, database in (
            ("primary", self.coyote_db),
            ("identity", self.identity_db),
            ("knowledgebase", self.knowledgebase_db),
            ("bam", self.bam_db),
        ):
            for attribute, collection in (
                self.app.config.get("DB_COLLECTIONS_CONFIG", {}).get(service, {}).items()
            ):
                setattr(self, attribute, database[collection])

    def _setup_repositories(self, *, ensure_indexes: bool = True):
        """
        Setup database operations repositories

        This method initializes various database operation repositories as attributes of the `MongoAdapter` instance.
        Each repository is responsible for managing a specific collection or set of operations in the database.
        """
        self.index_setup_conflicts: list[dict[str, str]] = []
        for repository_attr, repository_cls, _index_name in CORE_REPOSITORIES:
            setattr(self, repository_attr, repository_cls(self))
        for plugin in BUILTIN_KNOWLEDGEBASE_REPOSITORIES:
            setattr(self, plugin.repository_attr, plugin.repository_cls(self))
        if ensure_indexes:
            self.ensure_repository_indexes()

    def iter_repositories(self):
        """Yield registered repository names and instances in deterministic order."""
        for repository_attr, _repository_cls, index_name in CORE_REPOSITORIES:
            yield index_name, getattr(self, repository_attr)
        for plugin in BUILTIN_KNOWLEDGEBASE_REPOSITORIES:
            yield plugin.index_name, getattr(self, plugin.repository_attr)

    def ensure_repository_indexes(self) -> None:
        """Apply every registered repository's idempotent index contract."""
        for index_name, repository in self.iter_repositories():
            self._ensure_repository_indexes(index_name, repository)

    def verify_index_contracts(self) -> None:
        """Inspect required indexes without creating, changing, or dropping them."""
        from coyote_mongo.index_management import build_index_plan

        findings = [item for item in build_index_plan(self) if item["state"] != "present"]
        self.index_setup_conflicts = findings
        for item in findings:
            self.app.logger.warning(
                "Mongo index requires operator action repository=%s collection=%s "
                "index=%s state=%s. Run scripts/database/manage_mongo_indexes.py plan and apply "
                "during an approved maintenance window.",
                item["repository"],
                item["collection"],
                item["name"],
                item["state"],
            )

    def _ensure_repository_indexes(self, repository_name: str, repository: object) -> None:
        """Create indexes for a repository while tolerating historical index-name conflicts."""
        started = time.perf_counter()
        try:
            repository.ensure_indexes()
        except OperationFailure as exc:
            code = getattr(exc, "code", None)
            # MongoDB can report either IndexOptionsConflict (85) or
            # IndexKeySpecsConflict (86) when an existing deployment already has
            # a same-name or same-key index with different options. Do not block
            # API startup, but make the reconciliation action visible to ops.
            if code in {85, 86}:
                self.index_setup_conflicts.append(
                    {
                        "repository": repository_name,
                        "code": str(code),
                        "message": str(exc),
                    }
                )
                self.app.logger.warning(
                    (
                        "Mongo index conflict for repository=%s was tolerated at startup. "
                        "Review docs/operations/troubleshooting.md#mongo-index-conflicts, "
                        "compare db.<collection>.getIndexes(), then reconcile the index definition "
                        "during a maintenance window. Mongo error: %s"
                    ),
                    repository_name,
                    exc,
                )
                self.observe_operation(
                    operation=f"mongo_index_reconcile.{repository_name}",
                    outcome="conflict",
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                )
                return
            self.observe_operation(
                operation=f"mongo_index_reconcile.{repository_name}",
                outcome="failure",
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )
            raise
        self.observe_operation(
            operation=f"mongo_index_reconcile.{repository_name}",
            outcome="success",
            duration_ms=(time.perf_counter() - started) * 1000.0,
        )
