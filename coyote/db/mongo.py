import pymongo

from coyote.db.samples import SampleHandler
from coyote.db.users import UsersHandler

class MongoAdapter(SampleHandler,UsersHandler):
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