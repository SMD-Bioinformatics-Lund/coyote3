"""Capture and validate assay resources owned by an operational configuration revision."""

from copy import deepcopy
from hashlib import sha256
from typing import Any

from bson import json_util

from api.domain.common.errors import setup_error


def capture_assay_resource(panel: dict[str, Any]) -> dict[str, Any]:
    """Capture assay eligibility and identity without retaining a mutable resource reference.

    Args:
        panel: Validated assay revision selected by the configuration compiler.

    Returns:
        Independent resource content and a deterministic integrity digest.

    """
    content = deepcopy(panel)
    return {"content": content, "content_hash": _resource_hash(content)}


def _resource_hash(content: dict[str, Any]) -> str:
    """Hash BSON resource content with stable key ordering and explicit BSON types."""
    serialized = json_util.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        json_options=json_util.CANONICAL_JSON_OPTIONS,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def assay_resource(configuration: dict[str, Any]) -> dict[str, Any]:
    """Load the exact assay content captured by a configuration release.

    Args:
        configuration: Exact persisted configuration revision.

    Returns:
        A copy of the captured assay definition, including its eligibility genes.

    Raises:
        AppError: Content is absent, corrupt or belongs to a different assay or group.
    """
    release = configuration.get("assay_resource_release") or {}
    content = release.get("content")
    if not isinstance(content, dict) or release.get("content_hash") != _resource_hash(content):
        raise setup_error("Configuration assay resource is missing or has an invalid hash")
    if any(content.get(key) != configuration.get(key) for key in ("asp_id", "asp_group")):
        raise setup_error("Configuration assay resource does not match its assay and group")
    return deepcopy(content)


def capture_gene_lists(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Capture selectable gene-list revisions with an integrity digest.

    Args:
        documents: Eligible list revisions selected during release compilation.

    Returns:
        Independent documents keyed by registered list identity and their digest.

    Raises:
        AppError: Multiple revisions share a selectable identity.
    """
    content = {}
    for document in documents:
        identity = str(document["isgl_id"])
        if identity in content:
            raise setup_error(f"Multiple selectable revisions for gene list '{identity}'")
        content[identity] = deepcopy(document)
    return {"content": content, "content_hash": _resource_hash(content)}


def gene_list_resources(
    configuration: dict[str, Any], selected_ids: list[str] | None = None
) -> dict[str, Any]:
    """Load gene lists from the exact configuration revision.

    Args:
        configuration: Applied operational configuration revision.
        selected_ids: Selected identities; null returns all eligible lists while an empty
            list returns no selections.

    Returns:
        Independent list documents keyed by identity.

    Raises:
        AppError: Content is absent, corrupt or a selection is outside the release.
    """
    release = configuration.get("gene_list_release") or {}
    content = release.get("content")
    if not isinstance(content, dict) or release.get("content_hash") != _resource_hash(content):
        raise setup_error("Configuration gene lists are missing or have an invalid hash")
    if selected_ids is None:
        return deepcopy(content)
    missing = set(selected_ids) - content.keys()
    if missing:
        raise setup_error(
            "Gene lists are not available in the applied configuration: "
            + ", ".join(sorted(missing))
        )
    return {identity: deepcopy(content[identity]) for identity in selected_ids}
