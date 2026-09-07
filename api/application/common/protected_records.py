"""Rules shared by application-owned configuration records."""

from __future__ import annotations

from typing import Any, Mapping

from api.domain.common.errors import api_error


def reject_system_managed_delete(document: Mapping[str, Any], *, resource: str) -> None:
    """Reject deletion of a record installed with the application."""
    if bool(document.get("system_managed")):
        raise api_error(
            409,
            f"System-installed {resource} cannot be deleted. Deactivate it instead.",
        )
