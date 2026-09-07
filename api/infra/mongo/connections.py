"""Runtime-owned MongoDB connection pools shared by identical logical endpoints."""

from typing import Any

from pymongo import MongoClient
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from api.config.mongo import mongo_endpoints


class MongoConnections:
    """Own clients for one runtime/worker process, not for individual requests."""

    def __init__(self, config, *, client_factory=MongoClient):
        self.endpoints = mongo_endpoints(config)
        self._clients: dict[str, Any] = {}
        self.databases: dict[str, Any] = {}
        options = {
            "maxPoolSize": int(config.get("MONGO_MAX_POOL_SIZE", 100)),
            "minPoolSize": int(config.get("MONGO_MIN_POOL_SIZE", 0)),
            "connectTimeoutMS": int(config.get("MONGO_CONNECT_TIMEOUT_MS", 10_000)),
            "serverSelectionTimeoutMS": int(
                config.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", 30_000)
            ),
            "waitQueueTimeoutMS": int(config.get("MONGO_WAIT_QUEUE_TIMEOUT_MS", 10_000)),
        }
        configured_w = config.get("MONGO_WRITE_CONCERN_W", "majority")
        write_concern = WriteConcern(
            w=int(configured_w) if str(configured_w).isdigit() else configured_w,
            j=bool(config.get("MONGO_WRITE_CONCERN_JOURNAL", True)),
        )
        read_concern = ReadConcern(str(config.get("MONGO_READ_CONCERN_LEVEL", "majority")))
        try:
            for service, endpoint in self.endpoints.items():
                if endpoint.uri not in self._clients:
                    self._clients[endpoint.uri] = client_factory(endpoint.uri, **options)
                self.databases[service] = self._clients[endpoint.uri].get_database(
                    endpoint.database, read_concern=read_concern, write_concern=write_concern
                )
        except Exception:
            self.close()
            raise

    def ping(self):
        for client in self._clients.values():
            client.admin.command("ping")

    def close(self):
        for client in self._clients.values():
            client.close()
        self._clients.clear()
