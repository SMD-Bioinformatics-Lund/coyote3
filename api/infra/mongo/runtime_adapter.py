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
import pymongo
from pymongo.errors import OperationFailure

from api.infra.knowledgebase.plugins import enabled_knowledgebase_plugins
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
        self.translocation_repository = TranslocsRepository(self)
        self.copy_number_variant_repository = CNVsRepository(self)
        self.variant_repository = VariantsRepository(self)
        self.annotation_repository = AnnotationsRepository(self)
        self.sample_repository = SampleRepository(self)
        self.sample_comment_repository = SampleCommentsRepository(self)
        self.assay_panel_repository = ASPRepository(self)
        self.blacklist_repository = BlacklistRepository(self)
        self.expression_repository = ExpressionRepository(self)
        self.bam_record_repository = BamServiceRepository(self)
        self.user_repository = UsersRepository(self)
        self.fusion_repository = FusionsRepository(self)
        self.biomarker_repository = BiomarkerRepository(self)
        self.coverage_repository = CoverageRepository(self)
        self.grouped_coverage_repository = GroupCoverageRepository(self)
        self.assay_configuration_repository = ASPConfigRepository(self)
        self.roles_repository = RolesRepository(self)
        self.permissions_repository = PermissionsRepository(self)
        self.vep_metadata_repository = VEPMetaRepository(self)
        self.gene_list_repository = ISGLRepository(self)
        self.rna_expression_repository = RNAExpressionRepository(self)
        self.rna_classification_repository = RNAClassificationRepository(self)
        self.rna_quality_repository = RNAQCRepository(self)
        self.reported_variant_repository = ReportedVariantsRepository(self)
        self.report_repository = ReportRepository(self)
        self.dashboard_metrics_repository = DashboardMetricsRepository(self)
        for plugin in enabled_knowledgebase_plugins(self.app.config):
            setattr(self, plugin.repository_attr, plugin.repository_cls(self))
        self._ensure_repository_indexes("users", self.user_repository)
        self._ensure_repository_indexes("roles", self.roles_repository)
        self._ensure_repository_indexes("permissions", self.permissions_repository)
        self._ensure_repository_indexes("asp", self.assay_panel_repository)
        self._ensure_repository_indexes("aspc", self.assay_configuration_repository)
        self._ensure_repository_indexes("isgl", self.gene_list_repository)
        self._ensure_repository_indexes("samples", self.sample_repository)
        self._ensure_repository_indexes("sample_comments", self.sample_comment_repository)
        self._ensure_repository_indexes("annotations", self.annotation_repository)
        self._ensure_repository_indexes("variants", self.variant_repository)
        self._ensure_repository_indexes("biomarkers", self.biomarker_repository)
        self._ensure_repository_indexes("cnvs", self.copy_number_variant_repository)
        self._ensure_repository_indexes("translocs", self.translocation_repository)
        self._ensure_repository_indexes("fusions", self.fusion_repository)
        self._ensure_repository_indexes("blacklist", self.blacklist_repository)
        self._ensure_repository_indexes("coverage", self.coverage_repository)
        self._ensure_repository_indexes("groupcov", self.grouped_coverage_repository)
        self._ensure_repository_indexes("reported_variants", self.reported_variant_repository)
        self._ensure_repository_indexes("reports", self.report_repository)
        self._ensure_repository_indexes("dashboard_metrics", self.dashboard_metrics_repository)
        self._ensure_repository_indexes("vep_meta", self.vep_metadata_repository)
        self._ensure_repository_indexes("bam_service", self.bam_record_repository)
        self._ensure_repository_indexes("rna_expression", self.rna_expression_repository)
        self._ensure_repository_indexes("rna_classification", self.rna_classification_repository)
        self._ensure_repository_indexes("rna_qc", self.rna_quality_repository)
        self._ensure_repository_indexes("expression", self.expression_repository)
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
            # a compatible key pattern under the same/different name but older
            # options. Do not block API startup for that migration residue.
            if code in {85, 86}:
                self.app.logger.warning(
                    "Skipping index-name conflict for repository=%s: %s",
                    repository_name,
                    exc,
                )
                return
            raise
