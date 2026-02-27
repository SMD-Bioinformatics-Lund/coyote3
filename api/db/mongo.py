#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

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
from api.db.samples import SampleHandler
from api.db.users import UsersHandler
from api.db.asp import ASPHandler
from api.db.variants import VariantsHandler
from api.db.cnvs import CNVsHandler
from api.db.translocs import TranslocsHandler
from api.db.annotations import AnnotationsHandler
from api.db.expression import ExpressionHandler
from api.db.blacklist import BlacklistHandler
from api.db.oncokb import OnkoKBHandler
from api.db.bam_service import BamServiceHandler
from api.db.civic import CivicHandler
from api.db.iarc_tp53 import IARCTP53Handler
from api.db.brcaexchange import BRCAHandler
from api.db.fusions import FusionsHandler
from api.db.biomarkers import BiomarkerHandler
from api.db.coverage import CoverageHandler
from api.db.cosmic import CosmicHandler
from api.db.coverage2 import CoverageHandler2
from api.db.group_coverage import GroupCoverageHandler
from api.db.asp_configs import ASPConfigHandler
from api.db.schemas import SchemaHandler
from api.db.roles import RolesHandler
from api.db.permissions import PermissionsHandler
from api.db.vep_meta import VEPMetaHandler
from api.db.isgl import ISGLHandler
from api.db.hgnc import HGNCHandler
from api.db.rna_expression import RNAExpressionHandler
from api.db.rna_classification import RNAClassificationHandler
from api.db.rna_qc import RNAQCHandler
from api.db.reported_variants import ReportedVariantsHandler


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
        return self.app.config["MONGO_DB_NAME"]

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
            coyote_db: The primary database for the application, initialized using the `MONGO_DB_NAME` from the app's config.
            bam_db: The BAM service database, initialized using the `BAM_SERVICE_DB_NAME` from the app's config.
        """
        # No, set the db names from config:
        self.coyote_db = client[self.app.config["MONGO_DB_NAME"]]
        self.bam_db = client[self.app.config["BAM_SERVICE_DB_NAME"]]

    def setup(self) -> None:
        """
        Setup collections

        This method initializes the database collections for both the `coyote_db` and `bam_db` attributes.
        It retrieves the collection configurations from the application's configuration and sets them as attributes
        on the `MongoAdapter` instance for easy access.

        Collections for `coyote_db` are configured using the `DB_COLLECTIONS_CONFIG` dictionary with the key
        matching the `MONGO_DB_NAME` from the app's configuration. Similarly, collections for `bam_db` are
        configured using the `BAM_SERVICE_DB_NAME` key.

        Attributes:
            coyote_db: The primary database for the application.
            bam_db: The BAM service database.
        """
        # Coyote DB
        for collection_name, collection_value in (
            self.app.config.get("DB_COLLECTIONS_CONFIG", {})
            .get(self.app.config["MONGO_DB_NAME"], {})
            .items()
        ):
            setattr(self, collection_name, self.coyote_db[collection_value])

        # BAM Service DB
        for bam_collection_name, bam_collection_value in (
            self.app.config.get("DB_COLLECTIONS_CONFIG", {})
            .get(self.app.config["BAM_SERVICE_DB_NAME"], {})
            .items()
        ):
            setattr(self, bam_collection_name, self.bam_db[bam_collection_value])

    def _setup_handlers(self):
        """
        Setup database operations handlers

        This method initializes various database operation handlers as attributes of the `MongoAdapter` instance.
        Each handler is responsible for managing a specific collection or set of operations in the database.
        """
        self.transloc_handler = TranslocsHandler(self)
        self.cnv_handler = CNVsHandler(self)
        self.variant_handler = VariantsHandler(self)
        self.annotation_handler = AnnotationsHandler(self)
        self.sample_handler = SampleHandler(self)
        self.asp_handler = ASPHandler(self)
        self.civic_handler = CivicHandler(self)
        self.iarc_tp53_handler = IARCTP53Handler(self)
        self.brca_handler = BRCAHandler(self)
        self.blacklist_handler = BlacklistHandler(self)
        self.expression_handler = ExpressionHandler(self)
        self.bam_service_handler = BamServiceHandler(self)
        self.oncokb_handler = OnkoKBHandler(self)
        self.user_handler = UsersHandler(self)
        self.fusion_handler = FusionsHandler(self)
        self.biomarker_handler = BiomarkerHandler(self)
        self.coverage_handler = CoverageHandler(self)
        self.cosmic_handler = CosmicHandler(self)
        self.coverage2_handler = CoverageHandler2(self)
        self.groupcov_handler = GroupCoverageHandler(self)
        self.aspc_handler = ASPConfigHandler(self)
        self.schema_handler = SchemaHandler(self)
        self.roles_handler = RolesHandler(self)
        self.permissions_handler = PermissionsHandler(self)
        self.vep_meta_handler = VEPMetaHandler(self)
        self.isgl_handler = ISGLHandler(self)
        self.hgnc_handler = HGNCHandler(self)
        self.rna_expression_handler = RNAExpressionHandler(self)
        self.rna_classification_handler = RNAClassificationHandler(self)
        self.rna_qc_handler = RNAQCHandler(self)
        self.reported_variants_handler = ReportedVariantsHandler(self)
