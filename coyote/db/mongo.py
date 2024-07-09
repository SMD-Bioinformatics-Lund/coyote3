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
from coyote.db.fusions import FusionHandler


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
        self.samples_collection = self.coyote_db["samples"]
        self.users_collection = self.coyote_db["users"]
        self.groups_collection = self.coyote_db["groups"]
        self.panels_collection = self.coyote_db["panels"]
        self.variants_collection = self.coyote_db["variants_idref"]
        self.canonical_collection = self.coyote_db["refseq_canonical"]
        self.annotations_collection = self.coyote_db["annotation"]
        self.cnvs_collection = self.coyote_db["cnvs_wgs"]
        self.fusion_collection = self.coyote_db["fusions"]
        self.transloc_collection = self.coyote_db["transloc"]
        self.biomarkers_collection = self.coyote_db["biomarkers"]
        self.expression_collection = self.coyote_db["hpaexpr"]
        self.blacklist_collection = self.coyote_db["blacklist"]
        self.civic_variants_collection = self.coyote_db["civic_variants"]
        self.civic_gene_collection = self.coyote_db["civic_genes"]
        self.oncokb_collection = self.coyote_db["oncokb"]
        self.oncokb_actionable_collection = self.coyote_db["oncokb_actionable"]
        self.oncokb_genes_collection = self.coyote_db["oncokb_genes"]
        self.brcaexchange_collection = self.coyote_db["brcaexchange"]
        self.iarc_tp53_collection = self.coyote_db["iarc_tp53"]
        self.bam_samples = self.bam_db["samples"]

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
        self.fusion_handler = FusionHandler(self)
