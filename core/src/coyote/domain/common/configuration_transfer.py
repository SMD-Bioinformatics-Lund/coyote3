# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Portable configuration record boundaries, separate from application audit metadata."""

from __future__ import annotations

from typing import Any

CONFIGURATION_METADATA_FIELDS = frozenset(
    {
        "_id",
        "id_",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
        "created_on",
        "updated_on",
        "version",
        "content_version",
        "revision",
        "content_updated_at",
        "content_hash",
        "status",
        "active",
        "review",
        "lifecycle",
        "provenance",
        "content_editors",
        "system_installed",
        "system_managed",
        "version_history",
        "published_at",
        "published_on",
        "published_by",
        "retired_at",
        "retired_on",
        "retired_by",
        "retired_reason",
        "approved_at",
        "approved_by",
        "submitted_at",
        "submitted_by",
        "effective_from",
        "supersedes_id",
        "installed_by",
        "installed_on",
        "reviewer",
        "reviewed_by",
        "base_version",
        "is_current",
        "query_id",
        "scope_key",
        "rule_set_id",
        "catalog_key",
        "change_summary",
    }
)


def configuration_content(value: Any) -> Any:
    """Strip server-owned metadata at each submitted record boundary, preserving nested content."""
    if isinstance(value, list):
        return [configuration_content(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: nested for key, nested in value.items() if key not in CONFIGURATION_METADATA_FIELDS
    }
