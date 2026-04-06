"""
MongoAdapter module for Coyote3
===============================

This module defines the `MongoAdapter` class used for managing database connections
and initializing handlers for MongoDB operations.

It is part of the `coyote.db` package.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import pymongo
from pymongo.errors import OperationFailure

from api.infra.knowledgebase.plugins import enabled_knowledgebase_plugins
from api.infra.mongo.handlers.annotations import AnnotationsHandler
from api.infra.mongo.handlers.assay_configurations import ASPConfigHandler
from api.infra.mongo.handlers.assay_panels import ASPHandler
from api.infra.mongo.handlers.bam_records import BamServiceHandler
from api.infra.mongo.handlers.biomarkers import BiomarkerHandler
from api.infra.mongo.handlers.blacklist import BlacklistHandler
from api.infra.mongo.handlers.copy_number_variants import CNVsHandler
from api.infra.mongo.handlers.coverage import CoverageHandler
from api.infra.mongo.handlers.expression import ExpressionHandler
from api.infra.mongo.handlers.fusions import FusionsHandler
from api.infra.mongo.handlers.gene_lists import ISGLHandler
from api.infra.mongo.handlers.grouped_coverage import GroupCoverageHandler
from api.infra.mongo.handlers.permissions import PermissionsHandler
from api.infra.mongo.handlers.query_profiles import QueryProfilesHandler
from api.infra.mongo.handlers.reported_variants import ReportedVariantsHandler
from api.infra.mongo.handlers.rna_classification import RNAClassificationHandler
from api.infra.mongo.handlers.rna_expression import RNAExpressionHandler
from api.infra.mongo.handlers.rna_quality import RNAQCHandler
from api.infra.mongo.handlers.roles import RolesHandler
from api.infra.mongo.handlers.samples import SampleHandler
from api.infra.mongo.handlers.translocations import TranslocsHandler
from api.infra.mongo.handlers.users import UsersHandler
from api.infra.mongo.handlers.variants import VariantsHandler
from api.infra.mongo.handlers.vep_metadata import VEPMetaHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class MongoAdapter:
    """
    MongoAdapter Class

    This class manages database connections and initializes various handlers for database operations in a Flask application.
    It provides methods to set up database clients, configure collections, and initialize handlers for interacting with
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
            self._setup_handlers()  # Initialize handlers here only if client is provided

    def init_from_app(self, app) -> None:
        """
        Initialize the adapter using the application configuration.

        This method retrieves the MongoDB client using the `MONGO_URI` from the app's configuration,
        sets up the databases, and initializes the necessary handlers for database operations.

        Args:
            app: The Flask application instance containing the configuration.
        """
        self.client = self._get_mongoclient(app.config["MONGO_URI"])
        self.app = app
        self._setup_dbs(self.client)
        self.setup()
        self._setup_handlers()

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

    def _setup_handlers(self):
        """
        Setup database operations handlers

        This method initializes various database operation handlers as attributes of the `MongoAdapter` instance.
        Each handler is responsible for managing a specific collection or set of operations in the database.
        """
        self.translocation_handler = TranslocsHandler(self)
        self.copy_number_variant_handler = CNVsHandler(self)
        self.variant_handler = VariantsHandler(self)
        self.annotation_handler = AnnotationsHandler(self)
        self.sample_handler = SampleHandler(self)
        self.assay_panel_handler = ASPHandler(self)
        self.blacklist_handler = BlacklistHandler(self)
        self.expression_handler = ExpressionHandler(self)
        self.bam_record_handler = BamServiceHandler(self)
        self.user_handler = UsersHandler(self)
        self.fusion_handler = FusionsHandler(self)
        self.biomarker_handler = BiomarkerHandler(self)
        self.coverage_handler = CoverageHandler(self)
        self.grouped_coverage_handler = GroupCoverageHandler(self)
        self.assay_configuration_handler = ASPConfigHandler(self)
        self.roles_handler = RolesHandler(self)
        self.permissions_handler = PermissionsHandler(self)
        self.query_profile_handler = QueryProfilesHandler(self)
        self.vep_metadata_handler = VEPMetaHandler(self)
        self.gene_list_handler = ISGLHandler(self)
        self.rna_expression_handler = RNAExpressionHandler(self)
        self.rna_classification_handler = RNAClassificationHandler(self)
        self.rna_quality_handler = RNAQCHandler(self)
        self.reported_variant_handler = ReportedVariantsHandler(self)
        for plugin in enabled_knowledgebase_plugins(self.app.config):
            setattr(self, plugin.handler_attr, plugin.handler_cls(self))
        self._ensure_handler_indexes("users", self.user_handler)
        self._ensure_handler_indexes("roles", self.roles_handler)
        self._ensure_handler_indexes("permissions", self.permissions_handler)
        self._ensure_handler_indexes("query_profiles", self.query_profile_handler)
        self._ensure_handler_indexes("asp", self.assay_panel_handler)
        self._ensure_handler_indexes("aspc", self.assay_configuration_handler)
        self._ensure_handler_indexes("isgl", self.gene_list_handler)
        self._ensure_handler_indexes("samples", self.sample_handler)
        self._ensure_handler_indexes("annotations", self.annotation_handler)
        self._ensure_handler_indexes("variants", self.variant_handler)
        self._ensure_handler_indexes("biomarkers", self.biomarker_handler)
        self._ensure_handler_indexes("cnvs", self.copy_number_variant_handler)
        self._ensure_handler_indexes("translocs", self.translocation_handler)
        self._ensure_handler_indexes("fusions", self.fusion_handler)
        self._ensure_handler_indexes("blacklist", self.blacklist_handler)
        self._ensure_handler_indexes("coverage", self.coverage_handler)
        self._ensure_handler_indexes("groupcov", self.grouped_coverage_handler)
        self._ensure_handler_indexes("reported_variants", self.reported_variant_handler)
        self._ensure_handler_indexes("vep_meta", self.vep_metadata_handler)
        self._ensure_handler_indexes("bam_service", self.bam_record_handler)
        self._ensure_handler_indexes("rna_expression", self.rna_expression_handler)
        self._ensure_handler_indexes("rna_classification", self.rna_classification_handler)
        self._ensure_handler_indexes("rna_qc", self.rna_quality_handler)
        self._ensure_handler_indexes("expression", self.expression_handler)
        for plugin in enabled_knowledgebase_plugins(self.app.config):
            self._ensure_handler_indexes(plugin.index_name, getattr(self, plugin.handler_attr))
        self._ensure_dashboard_metrics_indexes()

    def _ensure_handler_indexes(self, handler_name: str, handler: object) -> None:
        """Create indexes for a handler while tolerating legacy index-name conflicts."""
        try:
            handler.ensure_indexes()
        except OperationFailure as exc:
            code = getattr(exc, "code", None)
            # pymongo 4 raises code 85 when index spec exists with another name.
            if code == 85:
                self.app.logger.warning(
                    "Skipping index-name conflict for handler=%s: %s",
                    handler_name,
                    exc,
                )
                return
            raise

    def _ensure_dashboard_metrics_indexes(self) -> None:
        """Ensure dashboard snapshot retention indexes."""
        ttl_seconds = int(
            self.app.config.get("DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS", 604800) or 0
        )
        if ttl_seconds <= 0:
            self.app.logger.info(
                "Dashboard snapshot TTL disabled (DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS=%s).",
                ttl_seconds,
            )
            return

        collection = self.coyote_db["dashboard_metrics"]
        try:
            collection.create_index(
                [("updated_at", pymongo.ASCENDING)],
                name="updated_at_ttl_1",
                expireAfterSeconds=ttl_seconds,
                background=True,
            )
        except OperationFailure as exc:
            code = getattr(exc, "code", None)
            if code == 85:
                self.app.logger.warning(
                    "Skipping dashboard_metrics TTL index conflict: %s",
                    exc,
                )
                return
            raise
