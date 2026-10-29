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
        "review_dependencies",
        "review_reason",
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
    """Copy portable records while removing application-owned audit fields.

    Args:
        value: One resource record, a list of records, or assay setup content.

    Returns:
        A copy without audit fields at each record boundary, descending only into
        setup panel, gene_lists and configurations. Arbitrary rule content, pinned
        references and predicate values remain unchanged. Non-record values pass
        through for the owning contract to validate; inputs are not mutated.
    """
    if isinstance(value, list):
        return [configuration_content(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: configuration_content(nested)
        if key in {"panel", "gene_lists", "configurations"}
        else nested
        for key, nested in value.items()
        if key not in CONFIGURATION_METADATA_FIELDS
    }
