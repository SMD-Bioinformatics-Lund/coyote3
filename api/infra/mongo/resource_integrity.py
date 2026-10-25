"""Canonical digest contract for persisted assay and gene-list releases.

Canonical Extended JSON is part of the persisted release format. Changing its type
encoding would invalidate existing release hashes, including integer and BSON values.
This module performs no persistence or runtime initialization.
"""

from hashlib import sha256
from typing import Any

from bson import json_util


def resource_content_hash(content: dict[str, Any]) -> str:
    """Digest release content using the established canonical BSON representation.

    Args:
        content: Assay document or identity-keyed gene-list documents.

    Returns:
        SHA-256 hexadecimal digest with deterministic key order and explicit BSON types.
    """
    serialized = json_util.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        json_options=json_util.CANONICAL_JSON_OPTIONS,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()
