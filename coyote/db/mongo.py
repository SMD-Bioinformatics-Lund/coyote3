import pymongo
from coyote.db.samples import SampleHandler
from coyote.db.users import UsersHandler
from coyote.db.group import GroupsHandler
from coyote.db.panels import PanelsHandler
from coyote.db.variants import VariantsHandler
from coyote.db.cnvs import CNVsHandler
from coyote.db.translocs import TranslocsHandler
from coyote.db.other import OtherHandler
from coyote.db.annotations import AnnotationsHandler
from coyote.db.expression import ExpressionHandler
from coyote.db.blacklist import BlacklistHandler
from coyote.db.oncokb import OnkoKBHandler
from coyote.db.bam_service import BamServiceHandler
from coyote.db.canonical import CanonicalHandler
from coyote.db.civic import CivicHandler
from coyote.db.iarc_tp53 import IARCTP53Handler
from coyote.db.brcaexchange import BRCAHandler
from coyote.db.fusions import FusionsHandler
from coyote.db.biomarkers import BiomarkerHandler
from coyote.db.coverage import CoverageHandler
from coyote.db.cosmic import CosmicHandler
from coyote.db.coverage2 import CoverageHandler2
from coyote.db.group_coverage import GroupCoverageHandler
from coyote.db.assay_configs import AssayConfigsHandler
from coyote.db.schemas import SchemaHandler


class MongoAdapter:
    def __init__(self, client: pymongo.MongoClient = None):
        self.client = client
        if self.client:
            self._setup_dbs(self.client)
            self._setup_handlers()  # Initialize handlers here only if client is provided

    def init_from_app(self, app) -> None:
        """
        Initialize the adapter from the app configuration
        """
        self.client = self._get_mongoclient(app.config["MONGO_URI"])
        self.app = app
        self._setup_dbs(self.client)
        self.setup()
        self._setup_handlers()

    def _get_mongoclient(self, mongo_uri: str) -> pymongo.MongoClient:
        return pymongo.MongoClient(mongo_uri)

    def _setup_dbs(self, client: pymongo.MongoClient) -> None:
        """
        Setup databases
        """
        # No, set the db names from config:
        self.coyote_db = client[self.app.config["MONGO_DB_NAME"]]
        self.bam_db = client[self.app.config["BAM_SERVICE_DB_NAME"]]

    def setup(self) -> None:
        """
        Setup collections
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
        """
        self.transloc_handler = TranslocsHandler(self)
        self.cnv_handler = CNVsHandler(self)
        self.variant_handler = VariantsHandler(self)
        self.annotation_handler = AnnotationsHandler(self)
        self.sample_handler = SampleHandler(self)
        self.panel_handler = PanelsHandler(self)
        self.canonical_handler = CanonicalHandler(self)
        self.civic_handler = CivicHandler(self)
        self.iarc_tp53_handler = IARCTP53Handler(self)
        self.brca_handler = BRCAHandler(self)
        self.blacklist_handler = BlacklistHandler(self)
        self.expression_handler = ExpressionHandler(self)
        self.bam_service_handler = BamServiceHandler(self)
        self.oncokb_handler = OnkoKBHandler(self)
        self.other_handler = OtherHandler(self)
        self.group_handler = GroupsHandler(self)
        self.user_handler = UsersHandler(self)
        self.fusion_handler = FusionsHandler(self)
        self.biomarker_handler = BiomarkerHandler(self)
        self.coverage_handler = CoverageHandler(self)
        self.cosmic_handler = CosmicHandler(self)
        self.coverage2_handler = CoverageHandler2(self)
        self.groupcov_handler = GroupCoverageHandler(self)
        self.assay_config_handler = AssayConfigsHandler(self)
        self.schema_handler = SchemaHandler(self)
