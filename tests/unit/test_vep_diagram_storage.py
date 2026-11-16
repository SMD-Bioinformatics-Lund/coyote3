"""Binary diagram migration, deduplication and seed integrity tests."""

import mongomock
import pytest
from coyote.contracts.schemas.variant_annotations import (
    VepConsequenceDiagramDoc,
)
from pydantic import ValidationError

from scripts.knowledgebase.update_vep_metadata import diagram_document
from scripts.knowledgebase.vep_diagram_storage import (
    split_diagram,
    store_diagram,
)


def image(release=116):
    """Return a validated synthetic SVG transport document."""
    return diagram_document(
        b'<svg viewBox="0 0 20 10"><rect width="20" height="10"/></svg>',
        "https://example.org/image.svg",
        release,
    )


def test_binary_storage_deduplicates_across_releases():
    db = mongomock.MongoClient().kb
    first = store_diagram(db, image(103))
    second = store_diagram(db, image(116))
    assert first["sha256"] == second["sha256"]
    assert db.vep_diagrams.count_documents({}) == 1
    assert isinstance(db.vep_diagrams.find_one()["data"], bytes)
    assert first["release"] == "103" and second["release"] == "116"
    with pytest.raises(ValidationError):
        VepConsequenceDiagramDoc.model_validate(image())


def test_checksum_mismatch_is_rejected_before_write():
    corrupt = {**image(), "sha256": "0" * 64}
    with pytest.raises(ValueError, match="checksum"):
        split_diagram(corrupt)
