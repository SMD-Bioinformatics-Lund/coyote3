"""Security and audit collection index setup."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from api.config.security import (
    get_api_sessions_collection_name,
    get_audit_events_collection_name,
)


@dataclass(frozen=True)
class SecurityIndexContract:
    """Index definition for security and operational collections."""

    collection: str
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
            (("expires_at", ASCENDING),),
            "ttl_api_session_expiry",
            {"expireAfterSeconds": 0},
        ),
        SecurityIndexContract(
            sessions,
            (("user_id", ASCENDING), ("expires_at", DESCENDING)),
            "idx_api_sessions_user_expiry",
        ),
        SecurityIndexContract(
            audit,
            (("expires_at", ASCENDING),),
            "ttl_audit_expiry",
            {"expireAfterSeconds": 0},
        ),
        SecurityIndexContract(audit, (("occurred_at", DESCENDING),), "idx_audit_occurred_at"),
        SecurityIndexContract(
            audit,
            (("severity", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_severity_time",
        ),
        SecurityIndexContract(
            audit,
            (("category", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_category_time",
        ),
        SecurityIndexContract(
            audit,
            (("event_type", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_event_type_time",
        ),
        SecurityIndexContract(
            audit,
            (("actor.username", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_actor_time",
        ),
        SecurityIndexContract(
            audit,
            (("tags", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_tags_time",
        ),
        SecurityIndexContract(
            audit,
            (("retention_class", ASCENDING), ("occurred_at", DESCENDING)),
            "idx_audit_retention_time",
        ),
        SecurityIndexContract(
            "app_controls",
            (("control_id", ASCENDING),),
            "uniq_app_controls_control_id",
            {"unique": True},
        ),
        SecurityIndexContract(
            "app_controls",
            (("updated_on", DESCENDING),),
            "idx_app_controls_updated_on",
        ),
    )


def ensure_security_indexes(*, db: Any, config: dict[str, Any], logger: logging.Logger) -> None:
    """Create session and audit indexes during an explicit maintenance operation."""
    for contract in security_index_contracts(config):
        _create_index(
            db[contract.collection],
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
