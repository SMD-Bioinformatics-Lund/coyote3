"""Load and verify bundled VEP diagram assets."""

import hashlib
import re
from pathlib import Path

from api.contracts.schemas.variant_annotations import (
    VepDiagramAssetDoc,
)


def load_seed_diagrams(documents: list[dict], reference_dir: Path) -> list[dict]:
    """Load unique binary assets referenced by a metadata seed, checking every hash.

    Args:
        documents: VEP metadata records containing compact diagram descriptors.
        reference_dir: Reference seed directory containing binary assets.

    Returns:
        MongoDB-ready records with native binary data and content-addressed IDs.

    Raises:
        ValueError: An asset identifier or checksum is invalid.
        OSError: A required asset is missing or unreadable.
    """
    result = {}
    for document in documents:
        diagram = document.get("consequence_diagram")
        if not diagram:
            continue
        digest = diagram["sha256"]
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Invalid VEP diagram asset identifier")
        content = (reference_dir / "vep_diagrams" / digest).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("VEP seed diagram checksum mismatch")
        result[digest] = VepDiagramAssetDoc.model_validate(
            {"_id": digest, "data": content, "mime_type": diagram["mime_type"]}
        ).model_dump(by_alias=True)
    return list(result.values())
