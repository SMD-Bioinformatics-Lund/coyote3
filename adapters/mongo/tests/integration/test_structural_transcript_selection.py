"""Embedded SnpEff selection preserves evidence and enforces sample ownership."""

from unittest.mock import Mock

import mongomock
from bson import ObjectId
from coyote_mongo.repositories.translocations import TranslocsRepository


def test_embedded_selection_preserves_rows_and_checks_concurrent_updates():
    """Only the owning sample's unchanged annotation array can be reordered."""
    collection = mongomock.MongoClient().db.translocations
    oid = ObjectId()
    first = {"Gene_Name": "A", "Feature_ID": "ENST000001"}
    second = {"Gene_Name": "A", "Feature_ID": "ENST000002"}
    original = [first, second]
    collection.insert_one(
        {
            "_id": oid,
            "SAMPLE_ID": "sample",
            "INFO": {"ANN": original, "MANE_ANN": first, "SVTYPE": "DEL"},
        }
    )
    repo = TranslocsRepository.__new__(TranslocsRepository)
    repo.get_collection = lambda: collection
    repo.invalidate_dashboard_metrics = Mock()
    assert repo.select_annotation(str(oid), "other", original, second).matched_count == 0
    assert repo.select_annotation(str(oid), "sample", original, second).matched_count == 1
    info = collection.find_one()["INFO"]
    assert info["ANN"] == [second, first]
    assert info["ANN_selection_source"] == "manual_override"
    assert "MANE_ANN" not in info
    assert info["SVTYPE"] == "DEL"
    assert repo.select_annotation(str(oid), "sample", original, first).matched_count == 0
