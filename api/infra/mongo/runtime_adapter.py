"""
MongoAdapter module for Coyote3
===============================

This module defines the `MongoAdapter` class used for managing database connections
and initializing repositories for MongoDB operations.

It is part of the MongoDB infrastructure layer.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import time
from typing import Any

from pymongo.errors import OperationFailure

from api.infra.knowledgebase.clinpgx_public import ClinPgxPublicRepository
from api.infra.knowledgebase.oncokb_public_cache import OncoKbPublicCacheRepository
from api.infra.knowledgebase.plugins import BUILTIN_KNOWLEDGEBASE_REPOSITORIES
from api.infra.mongo.connections import MongoConnections
from api.infra.mongo.repositories.anno_vep import AnnoVepRepository
from api.infra.mongo.repositories.annotations import AnnotationsRepository
from api.infra.mongo.repositories.assay_configurations import ASPConfigRepository
from api.infra.mongo.repositories.assay_panels import ASPRepository
from api.infra.mongo.repositories.bam_records import BamServiceRepository
from api.infra.mongo.repositories.biomarkers import BiomarkerRepository
from api.infra.mongo.repositories.blacklist import BlacklistRepository
from api.infra.mongo.repositories.clinical_rule_sets import (
    ClinicalRuleRevisionRepository,
    ClinicalRuleSetRepository,
)
from api.infra.mongo.repositories.copy_number_variants import CNVsRepository
from api.infra.mongo.repositories.coverage import CoverageRepository
from api.infra.mongo.repositories.expression import ExpressionRepository
from api.infra.mongo.repositories.finding_comments import FindingCommentsRepository
from api.infra.mongo.repositories.fusions import FusionsRepository
from api.infra.mongo.repositories.gene_lists import ISGLRepository
from api.infra.mongo.repositories.grouped_coverage import GroupCoverageRepository
from api.infra.mongo.repositories.ingest_jobs import IngestJobsRepository
from api.infra.mongo.repositories.notifications import NotificationsRepository
from api.infra.mongo.repositories.permissions import PermissionsRepository
from api.infra.mongo.repositories.pgx import PgxRepository
from api.infra.mongo.repositories.public_assay_catalog import PublicAssayCatalogRepository
from api.infra.mongo.repositories.public_assay_catalog_versions import (
    PublicAssayCatalogRevisionRepository,
    PublicAssayCatalogVersionRepository,
)
from api.infra.mongo.repositories.reported_variants import ReportedVariantsRepository
from api.infra.mongo.repositories.reports import ReportRepository
from api.infra.mongo.repositories.rna_classification import RNAClassificationRepository
from api.infra.mongo.repositories.rna_expression import RNAExpressionRepository
from api.infra.mongo.repositories.rna_quality import RNAQCRepository
from api.infra.mongo.repositories.roles import RolesRepository
from api.infra.mongo.repositories.sample_comments import SampleCommentsRepository
from api.infra.mongo.repositories.samples import SampleRepository
from api.infra.mongo.repositories.translocations import TranslocsRepository
from api.infra.mongo.repositories.users import UsersRepository
from api.infra.mongo.repositories.variants import VariantsRepository
from api.infra.mongo.repositories.vep_metadata import VEPMetaRepository
from api.infra.observability.prometheus_metrics import observe_operation

CORE_REPOSITORIES: tuple[tuple[str, type[Any], str], ...] = (
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
    ("blacklist_repository", BlacklistRepository, "blacklist"),
    ("expression_repository", ExpressionRepository, "expression"),
    ("bam_record_repository", BamServiceRepository, "bam_service"),
    ("user_repository", UsersRepository, "users"),
    ("fusion_repository", FusionsRepository, "fusions"),
    ("biomarker_repository", BiomarkerRepository, "biomarkers"),
    ("pgx_repository", PgxRepository, "pgx"),
    ("coverage_repository", CoverageRepository, "coverage"),
    ("grouped_coverage_repository", GroupCoverageRepository, "groupcov"),
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


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class MongoAdapter:
    """
    MongoAdapter Class

    This class manages database connections and initializes repositories for database operations in the API runtime.
    It provides methods to set up database clients, configure collections, and initialize repositories for interacting with
    different database collections.
    """

    def __init__(self):
        self.client = None
        self._connections = None

    def connect(self, app):
        """Bind logical databases without creating indexes or repositories."""
        self.app = app
        self._connections = MongoConnections(app.config)
        self.coyote_db = self._connections.databases["primary"]
        self.identity_db = self._connections.databases["identity"]
        self.knowledgebase_db = self._connections.databases["knowledgebase"]
        self.bam_db = self._connections.databases["bam"]
        # Existing app-owned transactions use the primary client only.
        self.client = self.coyote_db.client

    def close(self):
        if self._connections is not None:
            self._connections.close()

    def ping(self):
        self._connections.ping()

    def init_from_app(self, app) -> None:
        """Initialize repositories using independently configured MongoDB services."""
        try:
            self.connect(app)
            self.setup()
            self._setup_repositories(ensure_indexes=False)
            self.verify_index_contracts()
        except Exception:
            self.close()
            raise

    def get_db_name(self) -> str:
        return self.app.config["COYOTE3_DB"]

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
        from api.infra.mongo.index_management import build_index_plan

        findings = [item for item in build_index_plan(self) if item["state"] != "present"]
        self.index_setup_conflicts = findings
        for item in findings:
            self.app.logger.warning(
                "Mongo index requires operator action repository=%s collection=%s "
                "index=%s state=%s. Run scripts/manage_mongo_indexes.py plan and apply "
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
                observe_operation(
                    operation=f"mongo_index_reconcile.{repository_name}",
                    outcome="conflict",
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                )
                return
            observe_operation(
                operation=f"mongo_index_reconcile.{repository_name}",
                outcome="failure",
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )
            raise
        observe_operation(
            operation=f"mongo_index_reconcile.{repository_name}",
            outcome="success",
            duration_ms=(time.perf_counter() - started) * 1000.0,
        )
