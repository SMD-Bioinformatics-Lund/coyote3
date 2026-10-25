"""Assign record actors from trusted workflow context, preserving creation history."""

from collections.abc import Mapping
from typing import Any


def attribute_record(
    document: Mapping[str, Any],
    *,
    actor: str | None,
    previous: Mapping[str, Any] | None = None,
    system_installation: bool = False,
) -> dict[str, Any]:
    """Return content with server-owned actor and installation fields.

    Args:
        document: Proposed content; submitted attribution is not trusted.
        actor: Authenticated operator or explicit service identity; None if unknown.
        previous: Stored record when revising, or None for a new identity.
        system_installation: True only for the trusted application installer.

    Returns:
        Copy preserving the original creator on edits. Installed catalogs use
        ``system`` as their creator and updater, independently of the operator.
    """
    creator = "system" if system_installation else actor
    return {
        **document,
        "created_by": previous.get("created_by") if previous is not None else creator,
        "updated_by": creator,
        "system_installed": (
            bool(previous.get("system_installed")) if previous is not None else system_installation
        ),
        **(
            {"system_managed": bool((previous or {}).get("system_managed"))}
            if "system_managed" in document or previous is not None and "system_managed" in previous
            else {}
        ),
    }
