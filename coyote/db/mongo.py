import pymongo

from coyote.db.samples import SampleHandler
from coyote.db.users import UsersHandler
from coyote.db.group import GroupsHandler
from coyote.db.panels import PanelsHandler
from coyote.db.variants import VariantsHandler
from coyote.db.cnvs import CNVsHandler
from coyote.db.translocs import TranslocsHandler
from coyote.db.other import OtherHandler


class MongoAdapter(SampleHandler,UsersHandler,GroupsHandler,PanelsHandler,VariantsHandler,CNVsHandler,TranslocsHandler,OtherHandler):
    def __init__(self, client: pymongo.MongoClient = None):
        if client:
            self._setup_dbs(client)

    def init_from_app(self, app) -> None:
        client = self._get_mongoclient(app.config["MONGO_URI"])
        self._setup_dbs(client)
        self.setup()

    def _get_mongoclient(self, mongo_uri: str) -> pymongo.MongoClient:
        return pymongo.MongoClient(mongo_uri)

    def _setup_dbs(self, client: pymongo.MongoClient) -> None:
        # No, set the db names from config:
        self.coyote_db = client["coyote"]

    def setup(self) -> None:
        # coyote
        self.samples_collection = self.coyote_db["samples"]
        self.users_collection = self.coyote_db["users"]
        self.groups_collection = self.coyote_db["groups"]
        self.panels_collection = self.coyote_db["panels"]
        self.variants_collection = self.coyote_db["variants_idref"]
        self.canonical_collection = self.coyote_db["refseq_canonical"]
        self.annotations_collection = self.coyote_db["annotation"]
        self.cnvs_collection = self.coyote_db["cnvs_wgs"]
        self.transloc_collection = self.coyote_db["transloc"]
        self.biomarkers_collection = self.coyote_db["biomarkers"]
        