"""Security and audit collection index setup."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from api.config.contracts.application import OPERATIONAL_COLLECTIONS
from api.config.security import (
    get_api_sessions_collection_name,
    get_audit_events_collection_name,
)


@dataclass(frozen=True)
class SecurityIndexContract:
    """Index definition for security and operational collections."""

    collection: str
    database: str
    fields: tuple[tuple[str, int], ...]
    name: str
    options: dict[str, Any] = field(default_factory=dict)


def security_index_contracts(config: dict[str, Any]) -> tuple[SecurityIndexContract, ...]:
    """Return the canonical session, audit, and application-control indexes."""
    sessions = get_api_sessions_collection_name(config)
    audit = get_audit_events_collection_name(config)
    return (
        SecurityIndexContract(
            sessions,
            "identity",
            (("expires_at", ASCENDING),),
            "ttl_api_session_expiry",
            {"expireAfterSeconds": 0},
        ),
        SecurityIndexContract(
            sessions,
            "identity",
            (("user_id", ASCENDING), ("expires_at", DESCENDING)),
            "idx_api_sessions_user_expiry",
        ),
        SecurityIndexContract(
            audit,
            "identity",
            (("expires_at", ASCENDING),),
            "ttl_audit_expiry",
            {"expireAfterSeconds": 0},
        ),
        SecurityIndexContract(
            audit, "identity", (("occurred_at", DESCENDING),), "idx_audit_occurred_at"
        ),
        SecurityIndexContract(
            audit,
            "identity",
            (("severity", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_severity_time",
        ),
        SecurityIndexContract(
            audit,
            "identity",
            (("category", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_category_time",
        ),
        SecurityIndexContract(
            audit,
            "identity",
            (("event_type", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_event_type_time",
        ),
        SecurityIndexContract(
            audit,
            "identity",
            (("actor.username", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_actor_time",
        ),
        SecurityIndexContract(
            audit,
            "identity",
            (("tags", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_tags_time",
        ),
        SecurityIndexContract(
            audit,
            "identity",
            (("retention_class", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_retention_time",
        ),
        SecurityIndexContract(
            OPERATIONAL_COLLECTIONS.app_controls,
            "primary",
            (("control_id", ASCENDING),),
            "uniq_app_controls_control_id",
            {"unique": True},
        ),
        SecurityIndexContract(
            OPERATIONAL_COLLECTIONS.app_controls,
            "primary",
            (("updated_on", DESCENDING),),
            "idx_app_controls_updated_on",
        ),
    )


def ensure_security_indexes(
    *, primary_db: Any, identity_db: Any, config: dict[str, Any], logger: logging.Logger
) -> None:
    """Create session and audit indexes during an explicit maintenance operation."""
    for contract in security_index_contracts(config):
        database = identity_db if contract.database == "identity" else primary_db
        _create_index(
            database[contract.collection],
            list(contract.fields),
            name=contract.name,
            logger=logger,
            **contract.options,
        )


def _create_index(
    collection: Any, fields: list[tuple[str, int]], *, name: str, logger, **kwargs
) -> None:
    try:
        collection.create_index(fields, name=name, **kwargs)
    except PyMongoError as exc:
        logger.warning(
            "security_index_create_failed collection=%s index=%s error=%s",
            collection.name,
            name,
            exc,
        )
