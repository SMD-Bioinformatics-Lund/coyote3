"""Logical MongoDB endpoints, independent of database names and physical storage."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlsplit

MONGO_SERVICES = {
    "primary": ("COYOTE3_MONGO_URI", "COYOTE3_DB"),
    "identity": ("IDENTITY_MONGO_URI", "IDENTITY_DB"),
    "knowledgebase": ("KNOWLEDGEBASE_MONGO_URI", "KNOWLEDGEBASE_DB"),
    "bam": ("BAM_MONGO_URI", "BAM_DB"),
}


@dataclass(frozen=True)
class MongoEndpoint:
    uri: str = field(repr=False)
    database: str

    @property
    def namespace(self) -> tuple[tuple[str, ...], str, str]:
        """Compare deployment namespaces independently of user/authentication paths."""
        parsed = urlsplit(self.uri)
        hosts = tuple(sorted(parsed.netloc.rsplit("@", 1)[-1].lower().split(",")))
        replica_set = parse_qs(parsed.query).get("replicaSet", [""])[0]
        return hosts, replica_set, self.database


def configured_mongo_uri(config: Mapping[str, Any], service: str) -> str:
    """Resolve deployment values without implicit local defaults for maintenance CLIs."""
    uri_key, _ = MONGO_SERVICES[service]
    return str(
        config.get(uri_key) or config.get("COYOTE3_MONGO_URI") or config.get("MONGO_URI") or ""
    ).strip()


def mongo_uri(config: Mapping[str, Any], service: str) -> str:
    """Resolve an explicit endpoint, then the app endpoint, then the legacy URI.

    URI paths and authSource are left intact: neither selects the logical database.
    All environments require a configured URI; local examples belong in env templates.
    """
    uri_key, _ = MONGO_SERVICES[service]
    value = configured_mongo_uri(config, service)
    parsed = urlsplit(value)
    if parsed.scheme not in {"mongodb", "mongodb+srv"} or not parsed.netloc:
        raise RuntimeError(f"{uri_key} must be a configured MongoDB connection URI.")
    return value


def mongo_endpoints(config: Mapping[str, Any]) -> dict[str, MongoEndpoint]:
    """Validate logical database selections without deriving hosts from names."""
    endpoints = {}
    for service, (_, database_key) in MONGO_SERVICES.items():
        database = str(config.get(database_key) or "").strip()
        if not database:
            raise RuntimeError(f"{database_key} must be configured explicitly.")
        endpoints[service] = MongoEndpoint(mongo_uri(config, service), database)
    for service, endpoint in endpoints.items():
        for other, other_endpoint in endpoints.items():
            if service != other and endpoint.namespace == other_endpoint.namespace:
                raise RuntimeError(
                    f"{MONGO_SERVICES[service][1]} must be different from "
                    f"{MONGO_SERVICES[other][1]} on the same MongoDB endpoint."
                )
    return endpoints
