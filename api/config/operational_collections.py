"""Physical operational collection names owned by the MongoDB host."""

from dataclasses import dataclass
from typing import Final

from coyote3.config.contracts.application import APP_CONTROLS_ID


@dataclass(frozen=True)
class OperationalCollectionContract:
    """Names for internal collections that are part of the software contract."""

    api_sessions: str = "api_sessions"
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
