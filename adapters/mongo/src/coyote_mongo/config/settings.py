# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Explicit deployment inputs owned by the MongoDB adapter, without environment discovery."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from coyote.config.constants import DEFAULT_ENVIRONMENT
from coyote.config.policy import get_runtime_environment
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from coyote_mongo.config.collections import load_collection_mapping
from coyote_mongo.config.defaults import mongo_default
from coyote_mongo.config.endpoints import MongoEndpoint, mongo_endpoints


class AuditContext(BaseModel):
    """Immutable deployment identity supplied to transactional audit operations."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)
    environment: str
    route: str

    @classmethod
    def for_endpoint(cls, environment: str, endpoint: MongoEndpoint) -> AuditContext:
        """Derive the established route without retaining connection credentials.

        Args:
            environment: Deployment environment, accepting existing short and long labels.
            endpoint: Identity database endpoint whose credential-free namespace owns events.

        Returns:
            Normalized environment and stable routing digest used by existing queues.
        """
        environment = get_runtime_environment({"ENV_NAME": environment})
        route = sha256(repr((environment, endpoint.namespace)).encode()).hexdigest()
        return cls(environment=environment, route=route)


class MongoSettings(BaseModel):
    """Validated persistence inputs; API authentication and unrelated secrets are rejected."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", hide_input_in_errors=True, str_strip_whitespace=True
    )
    uri: SecretStr
    primary_database: str
    identity_database: str
    knowledgebase_database: str
    bam_database: str
    identity_uri: SecretStr = SecretStr("")
    knowledgebase_uri: SecretStr = SecretStr("")
    bam_uri: SecretStr = SecretStr("")
    environment: str = DEFAULT_ENVIRONMENT
    collections: dict[str, dict[str, str]] = Field(default_factory=load_collection_mapping)
    reports_root: Path | None = None
    sample_cache_ttl_seconds: int = Field(default=0, ge=0)
    metric_cache_fresh_seconds: int | None = None
    metric_cache_retention_seconds: int | None = None
    max_pool_size: int = Field(
        default_factory=lambda: mongo_default("MONGO_MAX_POOL_SIZE", int), ge=0
    )
    min_pool_size: int = Field(
        default_factory=lambda: mongo_default("MONGO_MIN_POOL_SIZE", int), ge=0
    )
    connect_timeout_ms: int = Field(
        default_factory=lambda: mongo_default("MONGO_CONNECT_TIMEOUT_MS", int), ge=0
    )
    server_selection_timeout_ms: int = Field(
        default_factory=lambda: mongo_default("MONGO_SERVER_SELECTION_TIMEOUT_MS", int), ge=0
    )
    wait_queue_timeout_ms: int = Field(
        default_factory=lambda: mongo_default("MONGO_WAIT_QUEUE_TIMEOUT_MS", int), ge=0
    )
    read_concern_level: str = Field(
        default_factory=lambda: mongo_default("MONGO_READ_CONCERN_LEVEL", str)
    )
    write_concern_w: str | int = Field(
        default_factory=lambda: mongo_default("MONGO_WRITE_CONCERN_W", str)
    )
    write_concern_journal: bool = Field(
        default_factory=lambda: mongo_default("MONGO_WRITE_CONCERN_JOURNAL", bool)
    )

    @model_validator(mode="after")
    def validate_endpoints(self) -> MongoSettings:
        """Reject missing or colliding logical databases before opening any connections."""
        mongo_endpoints(self.runtime_values())
        if self.max_pool_size and self.min_pool_size > self.max_pool_size:
            raise ValueError("min_pool_size must not exceed max_pool_size")
        return self

    @property
    def audit(self) -> AuditContext:
        """Return credential-free audit ownership for this adapter's identity endpoint."""
        endpoint = mongo_endpoints(self.runtime_values())["identity"]
        return AuditContext.for_endpoint(self.environment, endpoint)

    def runtime_values(self) -> dict[str, Any]:
        """Project adapter inputs into its existing collection and connection contracts.

        Returns:
            A fresh mapping containing only persistence, cache and artifact settings.
            URI values are unwrapped for PyMongo; callers must not log this mapping.
        """
        return {
            "COYOTE4_MONGO_URI": self.uri.get_secret_value(),
            "IDENTITY_MONGO_URI": self.identity_uri.get_secret_value(),
            "KNOWLEDGEBASE_MONGO_URI": self.knowledgebase_uri.get_secret_value(),
            "BAM_MONGO_URI": self.bam_uri.get_secret_value(),
            "COYOTE4_DB": self.primary_database,
            "IDENTITY_DB": self.identity_database,
            "KNOWLEDGEBASE_DB": self.knowledgebase_database,
            "BAM_DB": self.bam_database,
            "ENV_NAME": self.environment,
            "DB_COLLECTIONS_CONFIG": {key: dict(value) for key, value in self.collections.items()},
            "REPORTS_BASE_PATH": str(self.reports_root) if self.reports_root is not None else None,
            "CACHE_DEFAULT_TIMEOUT": self.sample_cache_ttl_seconds,
            "MONGO_MAX_POOL_SIZE": self.max_pool_size,
            "MONGO_MIN_POOL_SIZE": self.min_pool_size,
            "MONGO_CONNECT_TIMEOUT_MS": self.connect_timeout_ms,
            "MONGO_SERVER_SELECTION_TIMEOUT_MS": self.server_selection_timeout_ms,
            "MONGO_WAIT_QUEUE_TIMEOUT_MS": self.wait_queue_timeout_ms,
            "MONGO_READ_CONCERN_LEVEL": self.read_concern_level,
            "MONGO_WRITE_CONCERN_W": self.write_concern_w,
            "MONGO_WRITE_CONCERN_JOURNAL": self.write_concern_journal,
            **{
                key: value
                for key, value in (
                    ("DASHBOARD_METRIC_CACHE_TTL_SECONDS", self.metric_cache_fresh_seconds),
                    (
                        "DASHBOARD_METRIC_CACHE_RETENTION_SECONDS",
                        self.metric_cache_retention_seconds,
                    ),
                )
                if value is not None
            },
        }
