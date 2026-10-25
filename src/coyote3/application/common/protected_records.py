"""Rules shared by application-owned configuration records."""

from __future__ import annotations

from typing import Any, Mapping

from coyote3.domain.common.errors import api_error


def reject_system_managed_change(document: Mapping[str, Any], *, resource: str) -> None:
    """Reject administrative writes to an installed configuration definition.

    Args:
        document: Stored record whose ownership cannot be changed by submitted input.
        resource: User-facing record type.

    Raises:
        AppError: With status 409 for application-installed records.

    Notes:
        Password and authentication-state updates use dedicated security workflows.
        Controlled software installation is not an administrative CRUD operation.
    """
    if document.get("system_managed") or document.get("system_installed"):
        raise api_error(409, f"System-installed {resource} is read-only.")


def reject_system_managed_delete(document: Mapping[str, Any], *, resource: str) -> None:
    """Reject deletion of a record installed with the application."""
    if document.get("system_managed") or document.get("system_installed"):
        raise api_error(
            409,
            f"System-installed {resource} cannot be deleted.",
        )
