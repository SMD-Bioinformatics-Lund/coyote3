# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Physical operational collection names owned by the MongoDB host."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from coyote.config.contracts.application import APP_CONTROLS_ID


@dataclass(frozen=True)
class OperationalCollectionContract:
    """Names for internal collections that are part of the software contract."""

    api_sessions: str = "api_sessions"
    service_tokens: str = "service_tokens"
    audit_events: str = "audit_events"
    operational_audit_events: str = "operational_audit_events"
    audit_chain_heads: str = "audit_chain_heads"
    audit_outbox: str = "audit_outbox"
    report_artifact_erasure: str = "report_artifact_erasure"
    notification_activity_progress: str = "notification_activity_progress"
    app_controls: str = "app_controls"
    edit_leases: str = "edit_leases"
    app_controls_document_id: str = APP_CONTROLS_ID


OPERATIONAL_COLLECTIONS: Final = OperationalCollectionContract()


def get_api_sessions_collection_name(config: Mapping[str, Any]) -> str:
    """Return the MongoDB collection used for API sessions."""
    mappings = config.get("DB_COLLECTIONS_CONFIG") or {}
    identity_mapping = mappings.get("identity") if isinstance(mappings, Mapping) else None
    if isinstance(identity_mapping, Mapping):
        return str(
            identity_mapping.get("api_sessions_collection") or OPERATIONAL_COLLECTIONS.api_sessions
        )
    return OPERATIONAL_COLLECTIONS.api_sessions


def get_audit_events_collection_name(config: Mapping[str, Any]) -> str:
    """Return the MongoDB collection used for durable audit events."""
    mappings = config.get("DB_COLLECTIONS_CONFIG") or {}
    identity_mapping = mappings.get("identity") if isinstance(mappings, Mapping) else None
    if isinstance(identity_mapping, Mapping):
        return str(
            identity_mapping.get("audit_events_collection") or OPERATIONAL_COLLECTIONS.audit_events
        )
    return OPERATIONAL_COLLECTIONS.audit_events
