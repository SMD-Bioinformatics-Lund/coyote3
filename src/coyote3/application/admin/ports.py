"""Persistence operations required by runtime controls and retention workflows."""

from datetime import datetime
from typing import Any, Protocol


class AppControlsRepository(Protocol):
    """Store validated controls and remove expired operational audit records."""

    def read(self) -> dict[str, Any] | None:
        """Return current persisted controls or None before initialization."""
        ...

    def retention_override(self) -> dict[str, Any] | None:
        """Return the stored audit-retention override without unrelated settings."""
        ...

    def save(self, document: dict[str, Any], *, now: datetime) -> dict[str, Any]:
        """Persist validated fields while retaining original creation metadata."""
        ...

    def delete_operational_audit_before(self, cutoff: datetime) -> int:
        """Transactionally remove only operational audit records older than cutoff."""
        ...
