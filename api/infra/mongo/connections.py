"""Runtime-owned MongoDB connection pools shared by identical logical endpoints."""

from typing import Any

from pymongo import MongoClient
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from api.config.mongo import mongo_endpoints


class MongoConnections:
    """Own clients for one runtime/worker process, not for individual requests."""

    def __init__(self, config, *, client_factory=MongoClient):
        """Create shared clients and database handles for configured endpoints.

        Args:
            config: MongoDB endpoint, pool, timeout, and read/write concern settings.
            client_factory: Client constructor accepting a URI and pool options;
                defaults to PyMongo's ``MongoClient``.

        Notes:
            Endpoints with identical URIs share a client. If setup fails, clients
            already created are closed before the exception propagates.
        """
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
        """Ping each distinct client, propagating connection or command failures."""
        for client in self._clients.values():
            client.admin.command("ping")

    def close(self):
        """Close owned clients and clear the client registry."""
        for client in self._clients.values():
            client.close()
        self._clients.clear()
