"""Rules shared by application-owned configuration records."""

from __future__ import annotations

from typing import Any, Mapping

from api.domain.common.errors import api_error


def reject_system_managed_change(document: Mapping[str, Any], *, resource: str) -> None:
    """Reject administrative writes to an installed identity definition.

    Args:
        document: Stored record whose ownership cannot be changed by submitted input.
        resource: User-facing record type.

    Raises:
        AppError: With status 409 for application-installed records.

    Notes:
        Password and authentication-state updates use dedicated security workflows.
        Controlled software installation is not an administrative CRUD operation.
    """
    if bool(document.get("system_managed")):
        raise api_error(409, f"System-installed {resource} is read-only.")


def reject_system_managed_delete(document: Mapping[str, Any], *, resource: str) -> None:
    """Reject deletion of a record installed with the application."""
    if bool(document.get("system_managed")):
        raise api_error(
            409,
            f"System-installed {resource} cannot be deleted.",
        )
