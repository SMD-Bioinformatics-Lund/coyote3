"""Binary diagram migration, deduplication and seed integrity tests."""

import gzip
import json

import mongomock
import pytest
from pydantic import ValidationError

from api.contracts.schemas.reference import VepConsequenceDiagramDoc
from scripts.migrate_vep_diagram_storage import embedded_diagrams, migrate_seed
from scripts.update_vep_metadata import diagram_document
from scripts.vep_diagram_storage import load_seed_diagrams, split_diagram, store_diagram


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
    with pytest.raises(ValueError, match="checksum"):
        embedded_diagrams([{"vep_id": "116", "consequence_diagram": corrupt}])


def test_seed_migration_is_lossless_and_idempotent(tmp_path):
    source = image()
    seed = tmp_path / "vep_metadata.seed.ndjson.gz"
    row = {"vep_id": "116", "conseq_translations": {"unchanged": {}}, "consequence_diagram": source}
    seed.write_bytes(gzip.compress((json.dumps(row) + "\n").encode()))
    assert migrate_seed(seed) == 1
    assert migrate_seed(seed) == 0
    with gzip.open(seed, "rt") as stream:
        result = json.loads(stream.readline())
    assert result["conseq_translations"] == row["conseq_translations"]
    assert "data_base64" not in result["consequence_diagram"]
    assets = load_seed_diagrams([result], tmp_path)
    assert assets[0]["data"] == split_diagram(source)[1]
    assert embedded_diagrams([result]) == {}
    (tmp_path / "vep_diagrams" / source["sha256"]).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        load_seed_diagrams([result], tmp_path)
