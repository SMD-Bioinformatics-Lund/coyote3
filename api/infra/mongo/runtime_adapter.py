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
from typing import Any

import pymongo
from pymongo.errors import OperationFailure

from api.infra.knowledgebase.clinpgx_public import ClinPgxPublicRepository
from api.infra.knowledgebase.oncokb_public_cache import OncoKbPublicCacheRepository
from api.infra.knowledgebase.plugins import enabled_knowledgebase_plugins
from api.infra.mongo.repositories.anno_vep import AnnoVepRepository
from api.infra.mongo.repositories.annotations import AnnotationsRepository
from api.infra.mongo.repositories.assay_configurations import ASPConfigRepository
from api.infra.mongo.repositories.assay_panels import ASPRepository
from api.infra.mongo.repositories.bam_records import BamServiceRepository
from api.infra.mongo.repositories.biomarkers import BiomarkerRepository
from api.infra.mongo.repositories.blacklist import BlacklistRepository
from api.infra.mongo.repositories.clinical_rule_sets import ClinicalRuleSetRepository
from api.infra.mongo.repositories.copy_number_variants import CNVsRepository
from api.infra.mongo.repositories.coverage import CoverageRepository
from api.infra.mongo.repositories.dashboard_metrics import DashboardMetricsRepository
from api.infra.mongo.repositories.expression import ExpressionRepository
from api.infra.mongo.repositories.fusions import FusionsRepository
from api.infra.mongo.repositories.gene_lists import ISGLRepository
from api.infra.mongo.repositories.grouped_coverage import GroupCoverageRepository
from api.infra.mongo.repositories.permissions import PermissionsRepository
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
    ("coverage_repository", CoverageRepository, "coverage"),
    ("grouped_coverage_repository", GroupCoverageRepository, "groupcov"),
    ("assay_configuration_repository", ASPConfigRepository, "aspc"),
    ("roles_repository", RolesRepository, "roles"),
    ("permissions_repository", PermissionsRepository, "permissions"),
    ("vep_metadata_repository", VEPMetaRepository, "vep_meta"),
    ("gene_list_repository", ISGLRepository, "isgl"),
    ("rna_expression_repository", RNAExpressionRepository, "rna_expression"),
    ("rna_classification_repository", RNAClassificationRepository, "rna_classification"),
    ("rna_quality_repository", RNAQCRepository, "rna_qc"),
    ("reported_variant_repository", ReportedVariantsRepository, "reported_variants"),
    ("report_repository", ReportRepository, "reports"),
    ("clinical_rule_set_repository", ClinicalRuleSetRepository, "clinical_rule_sets"),
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
        self.client = self._get_mongoclient(app.config["MONGO_URI"])
        self.app = app
        self._setup_dbs(self.client)
        self.setup()
        self._setup_repositories()

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
        return pymongo.MongoClient(mongo_uri)

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
        self.coyote_db = client[self.app.config["COYOTE3_DB"]]
        self.bam_db = client[self.app.config["BAM_DB"]]

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

    def _setup_repositories(self):
        """
        Setup database operations repositories

        This method initializes various database operation repositories as attributes of the `MongoAdapter` instance.
        Each repository is responsible for managing a specific collection or set of operations in the database.
        """
        self.index_setup_conflicts: list[dict[str, str]] = []
        for repository_attr, repository_cls, _index_name in CORE_REPOSITORIES:
            setattr(self, repository_attr, repository_cls(self))
        for plugin in enabled_knowledgebase_plugins(self.app.config):
            setattr(self, plugin.repository_attr, plugin.repository_cls(self))
        for repository_attr, _repository_cls, index_name in CORE_REPOSITORIES:
            self._ensure_repository_indexes(index_name, getattr(self, repository_attr))
        for plugin in enabled_knowledgebase_plugins(self.app.config):
            self._ensure_repository_indexes(
                plugin.index_name, getattr(self, plugin.repository_attr)
            )

    def _ensure_repository_indexes(self, repository_name: str, repository: object) -> None:
        """Create indexes for a repository while tolerating historical index-name conflicts."""
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
                return
            raise
