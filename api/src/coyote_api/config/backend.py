# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Assemble package-specific settings at the backend's configuration boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from coyote.config.constants import DEFAULT_ENVIRONMENT
from coyote.config.public import PublicSettings
from coyote_mongo.config.defaults import MONGO_DEFAULTS
from coyote_mongo.config.endpoints import MongoEndpoint
from coyote_mongo.config.settings import AuditContext, MongoSettings


@dataclass(frozen=True)
class BackendSettings:
    """Validated package inputs assembled from the backend's resolved deployment settings."""

    mongo: MongoSettings
    public: PublicSettings

    @classmethod
    def from_runtime(cls, config: Mapping[str, Any]) -> BackendSettings:
        """Select persistence inputs without forwarding the backend's other settings.

        Args:
            config: Host-resolved environment, center and factory settings.

        Returns:
            Validated package configuration, independent of the source mapping.

        Raises:
            ValueError: A setting has the wrong type or a MongoDB selection is invalid.
            RuntimeError: A MongoDB URI or database name is missing or collides.
        """
        connection = {
            "max_pool_size": "MONGO_MAX_POOL_SIZE",
            "min_pool_size": "MONGO_MIN_POOL_SIZE",
            "connect_timeout_ms": "MONGO_CONNECT_TIMEOUT_MS",
            "server_selection_timeout_ms": "MONGO_SERVER_SELECTION_TIMEOUT_MS",
            "wait_queue_timeout_ms": "MONGO_WAIT_QUEUE_TIMEOUT_MS",
            "read_concern_level": "MONGO_READ_CONCERN_LEVEL",
            "write_concern_w": "MONGO_WRITE_CONCERN_W",
            "write_concern_journal": "MONGO_WRITE_CONCERN_JOURNAL",
        }
        return cls(
            public=public_settings_from_runtime(config),
            mongo=MongoSettings(
                uri=config.get("COYOTE4_MONGO_URI") or "",
                identity_uri=config.get("IDENTITY_MONGO_URI") or "",
                knowledgebase_uri=config.get("KNOWLEDGEBASE_MONGO_URI") or "",
                bam_uri=config.get("BAM_MONGO_URI") or "",
                primary_database=config.get("COYOTE4_DB") or "",
                identity_database=config.get("IDENTITY_DB") or "",
                knowledgebase_database=config.get("KNOWLEDGEBASE_DB") or "",
                bam_database=config.get("BAM_DB") or "",
                environment=config.get("ENV_NAME") or DEFAULT_ENVIRONMENT,
                **(
                    {"collections": config["DB_COLLECTIONS_CONFIG"]}
                    if config.get("DB_COLLECTIONS_CONFIG") is not None
                    else {}
                ),
                reports_root=config.get("REPORTS_BASE_PATH"),
                sample_cache_ttl_seconds=config.get("CACHE_DEFAULT_TIMEOUT", 0),
                metric_cache_fresh_seconds=config.get("DASHBOARD_METRIC_CACHE_TTL_SECONDS"),
                metric_cache_retention_seconds=config.get(
                    "DASHBOARD_METRIC_CACHE_RETENTION_SECONDS"
                ),
                **{
                    field: config.get(key, MONGO_DEFAULTS[key]) for field, key in connection.items()
                },
            ),
        )


def audit_context_from_runtime(config: Mapping[str, Any]) -> AuditContext:
    """Select audit ownership for host maintenance tools without passing unrelated settings.

    Args:
        config: Host environment or resolved runtime configuration.

    Returns:
        Credential-free deployment identity for an explicit identity endpoint.

    Raises:
        RuntimeError: The identity endpoint or database is not configured.
    """
    from coyote_mongo.config.endpoints import mongo_uri

    selected = {
        key: config.get(key) for key in ("COYOTE4_MONGO_URI", "IDENTITY_MONGO_URI", "IDENTITY_DB")
    }
    if not selected["IDENTITY_DB"]:
        raise RuntimeError("IDENTITY_DB must be configured for transactional audit routing")
    return AuditContext.for_endpoint(
        str(config.get("ENV_NAME") or DEFAULT_ENVIRONMENT),
        MongoEndpoint(mongo_uri(selected, "identity"), str(selected["IDENTITY_DB"])),
    )


def public_settings_from_runtime(config: Mapping[str, Any]) -> PublicSettings:
    """Select public reference-service inputs without forwarding backend settings.

    Args:
        config: Host-resolved runtime settings.

    Returns:
        Core-owned settings containing only public reference-service availability.
    """
    return PublicSettings(
        oncokb_configured=bool(config.get("ONCOKB_BASE_URL")),
        clinpgx_configured=bool(config.get("CLINPGX_BASE_URL")),
    )
