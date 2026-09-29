"""Reference-link repairs preserve definitions, provenance and image content."""

import copy
import gzip
import json

import mongomock
import pytest
from bson import decode_all

from scripts import repair_vep_reference_links as repair
from scripts.update_vep_metadata import reference_links


@pytest.mark.parametrize("release,archive", [(98, "sep2019"), (103, "feb2021"), (116, "jun2026")])
def test_links_target_the_selected_release(release, archive):
    links = reference_links(release)
    assert all(
        url.startswith(f"https://{archive}.archive.ensembl.org/info/") for url in links.values()
    )
    assert links["conseq_translation_source"].endswith("/predicted_data.html")
    assert links["vc_translation_source"].endswith("/classification.html")
    assert links["source"].endswith("/vep_cache.html")


def test_unknown_archive_is_not_guessed():
    with pytest.raises(ValueError, match="Unreviewed"):
        reference_links(999)


def test_repairs_preserve_all_unrelated_fields_and_are_idempotent(tmp_path, monkeypatch):
    original = {
        "_id": "reference",
        "vep_id": "103",
        "source": "old-url",
        "conseq_translations": {"example": {"desc": "unchanged"}},
        "consequence_diagram": {"data_base64": "original", "source_url": "pinned-url"},
        "db_info": {
            "GRCh37": {
                "published_sources": {
                    "Ensembl database version": "[[SPECIESDEFS::ENSEMBL_VERSION]]",
                    "MANE": "v1.5",
                }
            }
        },
    }
    collection = mongomock.MongoClient().kb.vep_metadata
    collection.insert_one(copy.deepcopy(original))
    monkeypatch.setattr(repair, "run_transaction", lambda client, operation: operation(None))
    backup = tmp_path / "before.bson"
    assert repair.install(collection, backup) == 1
    assert decode_all(backup.read_bytes()) == [original]
    updated = collection.find_one({})
    assert updated["conseq_translations"] == original["conseq_translations"]
    assert updated["consequence_diagram"] == original["consequence_diagram"]
    assert updated["db_info"]["GRCh37"]["published_sources"] == {
        "Ensembl database version": "103",
        "MANE": "v1.5",
    }
    assert repair.corrections(updated) == {}
    seed = tmp_path / "seed.gz"
    seed.write_bytes(gzip.compress((json.dumps(original) + "\n").encode()))
    assert repair.update_seed(seed) == 1
    with gzip.open(seed, "rt") as stream:
        assert json.loads(stream.readline()) == updated
    assert repair.update_seed(seed) == 0


def test_concurrent_changes_abort_repair(tmp_path, monkeypatch):
    collection = mongomock.MongoClient().kb.vep_metadata
    collection.insert_one({"vep_id": "116"})

    def concurrent(client, operation):
        """Simulate a reference import occurring after the backup."""
        collection.update_one({}, {"$set": {"source": "concurrent"}})
        operation(None)

    monkeypatch.setattr(repair, "run_transaction", concurrent)
    with pytest.raises(RuntimeError, match="changed after backup"):
        repair.install(collection, tmp_path / "before.bson")
    assert collection.find_one({})["source"] == "concurrent"
