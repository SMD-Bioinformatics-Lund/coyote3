"""Structural finding repositories retain their existing MongoDB index contracts."""

from types import SimpleNamespace

import mongomock
import pytest
from coyote_mongo.repositories.copy_number_variants import CNVsRepository
from coyote_mongo.repositories.fusions import FusionsRepository
from coyote_mongo.repositories.translocations import TranslocsRepository


@pytest.mark.parametrize(
    "repository_type,binding",
    [
        (CNVsRepository, "cnvs_collection"),
        (TranslocsRepository, "transloc_collection"),
        (FusionsRepository, "fusions_collection"),
    ],
)
def test_finding_indexes_preserve_names_keys_and_unrelated_data(repository_type, binding):
    """Repeated setup retains data and creates indexes only on the bound collection."""
    database = mongomock.MongoClient().synthetic
    collection = database.findings
    collection.insert_one({"_id": "synthetic", "SAMPLE_ID": "sample", "interesting": True})
    database.unrelated.insert_one({"_id": "unrelated"})
    repository = repository_type(SimpleNamespace(**{binding: collection}))

    repository.ensure_indexes()
    expected = {
        "_id_": [("_id", 1)],
        "sample_id_1": [("SAMPLE_ID", 1)],
        "sample_id_1_interesting_1": [("SAMPLE_ID", 1), ("interesting", 1)],
        "sample_id_1_fp_1": [("SAMPLE_ID", 1), ("fp", 1)],
        "sample_id_1_irrelevant_1": [("SAMPLE_ID", 1), ("irrelevant", 1)],
    }
    if repository_type is FusionsRepository:
        expected["calls_breakpoint1_1_calls_breakpoint2_1_sample_id_1"] = [
            ("calls.breakpoint1", 1),
            ("calls.breakpoint2", 1),
            ("SAMPLE_ID", 1),
        ]
    before = collection.index_information()
    assert {name: info["key"] for name, info in before.items()} == expected
    repository.ensure_indexes()
    assert collection.index_information() == before
    assert collection.find_one({"_id": "synthetic"})["interesting"] is True
    assert list(database.unrelated.index_information()) == ["_id_"]
