"""Persistence and diagnostic-context ports required by audit workflows."""

from typing import Any, Protocol


class AuditRepository(Protocol):
    """Persist audit events and replay pending deliveries without exposing storage handles."""

    def persist(self, document: dict[str, Any]) -> str | None:
        """Assign a stable identifier and durably accept a sanitized audit event."""
        ...

    def replay_pending(self, *, environment: str) -> int:
        """Deliver pending events for the configured environment and return the count."""
        ...

    def recent_events(self, *, limit: int) -> dict[str, Any]:
        """Return bounded recent events and the total event count."""
        ...


class AuditRequestContext(Protocol):
    """Optional transport diagnostics supplied by the entry point, never read globally."""

    request_id: str
    client_ip: str | None
    method: str
    path: str
    user_agent: str | None
