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

import pymongo
from pymongo.errors import OperationFailure
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from api.infra.knowledgebase.clinpgx_public import ClinPgxPublicRepository
from api.infra.knowledgebase.oncokb_public_cache import OncoKbPublicCacheRepository
from api.infra.knowledgebase.plugins import BUILTIN_KNOWLEDGEBASE_REPOSITORIES
from api.infra.mongo.repositories.anno_vep import AnnoVepRepository
from api.infra.mongo.repositories.annotations import AnnotationsRepository
from api.infra.mongo.repositories.assay_configurations import ASPConfigRepository
from api.infra.mongo.repositories.assay_panels import ASPRepository
from api.infra.mongo.repositories.bam_records import BamServiceRepository
from api.infra.mongo.repositories.biomarkers import BiomarkerRepository
from api.infra.mongo.repositories.blacklist import BlacklistRepository
from api.infra.mongo.repositories.copy_number_variants import CNVsRepository
from api.infra.mongo.repositories.coverage import CoverageRepository
from api.infra.mongo.repositories.dashboard_metrics import DashboardMetricsRepository
from api.infra.mongo.repositories.expression import ExpressionRepository
from api.infra.mongo.repositories.fusions import FusionsRepository
from api.infra.mongo.repositories.gene_lists import ISGLRepository
from api.infra.mongo.repositories.grouped_coverage import GroupCoverageRepository
from api.infra.mongo.repositories.notifications import NotificationsRepository
from api.infra.mongo.repositories.permissions import PermissionsRepository
from api.infra.mongo.repositories.pgx import PgxRepository
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
    ("sample_comment_repository", SampleCommentsRepository, "sample_comments"),
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
    ("dashboard_metrics_repository", DashboardMetricsRepository, "dashboard_metrics"),
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

    def __init__(self, client: pymongo.MongoClient = None):
        """__init__.

        Args:
                client: Client. Optional argument.
        """
        self.client = client
        if self.client:
            self._setup_dbs(self.client)
            self._setup_repositories()  # Initialize repositories here only if client is provided

    def init_from_app(self, app) -> None:
        """
        Initialize the adapter using the application configuration.

        This method retrieves the MongoDB client using the `MONGO_URI` from the app's configuration,
        sets up the databases, and initializes the necessary repositories for database operations.

        Args:
            app: Runtime object containing the API configuration.
        """
        self.app = app
        self.client = self._get_mongoclient(app.config["MONGO_URI"])
        self._setup_dbs(self.client)
        self.setup()
        self._setup_repositories(ensure_indexes=False)
        self.verify_index_contracts()

    def get_db_name(self) -> str:
        """
        Get the name of the primary database.

        Returns:
         str: The name of the primary database as specified in the application's configuration.
        """
        return self.app.config["COYOTE3_DB"]

    def _get_mongoclient(self, mongo_uri: str) -> pymongo.MongoClient:
        """
        Retrieve a MongoDB client instance.

        Args:
         mongo_uri (str): The MongoDB connection URI.

        Returns:
         pymongo.MongoClient: A MongoDB client instance connected to the specified URI.
        """
        return pymongo.MongoClient(
            mongo_uri,
            maxPoolSize=int(self.app.config.get("MONGO_MAX_POOL_SIZE", 100)),
            minPoolSize=int(self.app.config.get("MONGO_MIN_POOL_SIZE", 0)),
            connectTimeoutMS=int(self.app.config.get("MONGO_CONNECT_TIMEOUT_MS", 10_000)),
            serverSelectionTimeoutMS=int(
                self.app.config.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", 30_000)
            ),
            waitQueueTimeoutMS=int(self.app.config.get("MONGO_WAIT_QUEUE_TIMEOUT_MS", 10_000)),
        )

    def _setup_dbs(self, client: pymongo.MongoClient) -> None:
        """
        Setup databases

        This method configures the database connections for the `coyote_db` and `bam_db` attributes
        using the database names specified in the application's configuration.

        Attributes:
            coyote_db: The primary database for the application, initialized using the `COYOTE3_DB` from the app's config.
            bam_db: The BAM service database, initialized using the `BAM_DB` from the app's config.
        """
        # No, set the db names from config:
        read_concern = ReadConcern(
            level=str(self.app.config.get("MONGO_READ_CONCERN_LEVEL", "majority"))
        )
        configured_w = self.app.config.get("MONGO_WRITE_CONCERN_W", "majority")
        write_w = int(configured_w) if str(configured_w).isdigit() else configured_w
        write_concern = WriteConcern(
            w=write_w,
            j=bool(self.app.config.get("MONGO_WRITE_CONCERN_JOURNAL", True)),
        )
        self.coyote_db = client.get_database(self.app.config["COYOTE3_DB"]).with_options(
            read_concern=read_concern, write_concern=write_concern
        )
        self.bam_db = client.get_database(self.app.config["BAM_DB"]).with_options(
            read_concern=read_concern, write_concern=write_concern
        )

    def setup(self) -> None:
        """
        Setup collections

        This method initializes the database collections for both the `coyote_db` and `bam_db` attributes.
        It retrieves the collection configurations from the application's configuration and sets them as attributes
        on the `MongoAdapter` instance for easy access.

        Collections for `coyote_db` are configured using the `DB_COLLECTIONS_CONFIG` dictionary with the key
        matching the `COYOTE3_DB` from the app's configuration. Similarly, collections for `bam_db` are
        configured using the `BAM_DB` key.

        Attributes:
            coyote_db: The primary database for the application.
            bam_db: The BAM service database.
        """
        # Coyote DB
        for collection_name, collection_value in (
            self.app.config.get("DB_COLLECTIONS_CONFIG", {})
            .get(self.app.config["COYOTE3_DB"], {})
            .items()
        ):
            setattr(self, collection_name, self.coyote_db[collection_value])

        # BAM Service DB
        for bam_collection_name, bam_collection_value in (
            self.app.config.get("DB_COLLECTIONS_CONFIG", {})
            .get(self.app.config["BAM_DB"], {})
            .items()
        ):
            setattr(self, bam_collection_name, self.bam_db[bam_collection_value])

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
