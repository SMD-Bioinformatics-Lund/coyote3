"""Security and audit collection index setup."""

from __future__ import annotations

import logging
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from api.config.security import (
    get_api_sessions_collection_name,
    get_audit_events_collection_name,
)


def ensure_security_indexes(*, db: Any, config: dict[str, Any], logger: logging.Logger) -> None:
    """Create session and audit indexes without rewriting existing data."""
    sessions = db[get_api_sessions_collection_name(config)]
    audit = db[get_audit_events_collection_name(config)]
    controls = db["app_controls"]
    _create_index(
        sessions,
        [("expires_at", ASCENDING)],
        name="ttl_api_session_expiry",
        expireAfterSeconds=0,
        logger=logger,
    )
    _create_index(
        sessions,
        [("user_id", ASCENDING), ("expires_at", DESCENDING)],
        name="idx_api_sessions_user_expiry",
        logger=logger,
    )
    _create_index(
        audit,
        [("expires_at", ASCENDING)],
        name="ttl_audit_expiry",
        expireAfterSeconds=0,
        logger=logger,
    )
    for fields, name in (
        ([("occurred_at", DESCENDING)], "idx_audit_occurred_at"),
        ([("severity", ASCENDING), ("occurred_at", DESCENDING)], "idx_audit_severity_time"),
        ([("category", ASCENDING), ("occurred_at", DESCENDING)], "idx_audit_category_time"),
        ([("event_type", ASCENDING), ("occurred_at", DESCENDING)], "idx_audit_event_type_time"),
        ([("actor.username", ASCENDING), ("occurred_at", DESCENDING)], "idx_audit_actor_time"),
        ([("tags", ASCENDING), ("occurred_at", DESCENDING)], "idx_audit_tags_time"),
        (
            [("retention_class", ASCENDING), ("occurred_at", DESCENDING)],
            "idx_audit_retention_time",
        ),
    ):
        _create_index(audit, fields, name=name, logger=logger)
    _create_index(
        controls,
        [("control_id", ASCENDING)],
        name="uniq_app_controls_control_id",
        unique=True,
        logger=logger,
    )
    _create_index(
        controls,
        [("updated_on", DESCENDING)],
        name="idx_app_controls_updated_on",
        logger=logger,
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
