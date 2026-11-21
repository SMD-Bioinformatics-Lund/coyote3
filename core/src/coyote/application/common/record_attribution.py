# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Assign record actors from trusted workflow context, preserving creation history."""

from collections.abc import Mapping
from functools import lru_cache
from typing import Any

from coyote.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS


@lru_cache(maxsize=None)
def _attribution_fields(collection: str) -> frozenset[str]:
    """Return the attribution fields declared by the destination contract."""
    return frozenset(COLLECTION_MODEL_ADAPTERS[collection].json_schema()["properties"])


def attribute_record(
    document: Mapping[str, Any],
    *,
    actor: str | None,
    previous: Mapping[str, Any] | None = None,
    system_installation: bool = False,
    collection: str | None = None,
) -> dict[str, Any]:
    """Return content with server-owned actor and installation fields.

    Args:
        document: Proposed content; submitted attribution is not trusted.
        actor: Authenticated operator or explicit service identity; None if unknown.
        previous: Stored record when revising, or None for a new identity.
        system_installation: True only for the trusted application installer.
        collection: Destination contract; omit only for configuration-only callers.

    Returns:
        Copy preserving the original creator on edits. Installed catalogs use
        ``system`` as their creator and updater, independently of the operator.
    """
    creator = "system" if system_installation else actor
    result = {
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

    if collection is not None:
        supported = _attribution_fields(collection)
        for key in ("created_by", "updated_by", "system_installed"):
            if key not in supported:
                result.pop(key, None)
    return result
