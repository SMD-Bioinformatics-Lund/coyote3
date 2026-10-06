"""Store validated VEP diagrams separately from release metadata."""

import base64
import hashlib
import re
from pathlib import Path

from api.config.loaders.collections import load_collection_section
from api.contracts.schemas.reference import VepDiagramAssetDoc


def split_diagram(diagram: dict) -> tuple[dict, bytes]:
    """Extract and verify downloaded image bytes before persistence.

    Args:
        diagram: Validated downloader output containing base64 transport data.

    Returns:
        Compact metadata descriptor and original bytes.

    Raises:
        ValueError: Image bytes do not match their declared hash.
    """
    descriptor = {key: value for key, value in diagram.items() if key != "data_base64"}
    content = base64.b64decode(diagram["data_base64"], validate=True)
    if hashlib.sha256(content).hexdigest() != descriptor["sha256"]:
        raise ValueError("VEP diagram checksum mismatch")
    return descriptor, content


def store_diagram(database, diagram: dict, session=None) -> dict:
    """Upsert original bytes by SHA-256, returning only the metadata descriptor.

    Args:
        database: Knowledgebase database sharing the metadata transaction client.
        diagram: Validated downloader output with image transport data.
        session: Metadata transaction session, or None for independent installation.

    Returns:
        Descriptor without base64 data.
    """
    descriptor, content = split_diagram(diagram)
    asset = VepDiagramAssetDoc.model_validate(
        {"_id": descriptor["sha256"], "data": content, "mime_type": descriptor["mime_type"]}
    ).model_dump(by_alias=True)
    collection = load_collection_section("knowledgebase")["vep_diagrams_collection"]
    database[collection].update_one(
        {"_id": descriptor["sha256"]},
        {"$setOnInsert": asset},
        upsert=True,
        session=session,
    )
    return descriptor


def seed_diagram(diagram: dict, reference_dir: Path) -> dict:
    """Retain binary seed assets separately from compressed metadata JSON.

    Args:
        diagram: Validated downloader output.
        reference_dir: Reference seed directory owning a vep_diagrams subdirectory.

    Returns:
        Compact diagram descriptor for the metadata seed.
    """
    descriptor, content = split_diagram(diagram)
    directory = reference_dir / "vep_diagrams"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / descriptor["sha256"]).write_bytes(content)
    return descriptor


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
