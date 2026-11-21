"""Interval storage remains sample-scoped and separate from D4 summaries."""

from types import SimpleNamespace

import mongomock
from coyote_mongo.repositories.coverage import CoverageRepository


def test_interval_repository_reads_only_the_selected_sample_and_keeps_zero_depth():
    database = mongomock.MongoClient().synthetic
    database.coverage.insert_many(
        [
            {
                "_id": "later",
                "SAMPLE_ID": "owner",
                "chr": "7",
                "start": 20,
                "end": 30,
                "avg_cov": 2.5,
            },
            {"_id": "first", "SAMPLE_ID": "owner", "chr": "7", "start": 0, "end": 10, "avg_cov": 0},
            {
                "_id": "other",
                "SAMPLE_ID": "different",
                "chr": "7",
                "start": 0,
                "end": 10,
                "avg_cov": 0,
            },
        ]
    )
    repository = CoverageRepository(SimpleNamespace(coverage_collection=database.coverage))
    repository.ensure_indexes()
    repository.ensure_indexes()
    rows = repository.get_sample_intervals("owner")
    assert [row["_id"] for row in rows] == ["first", "later"]
    assert rows[0]["avg_cov"] == 0
    assert repository.get_sample_intervals("absent") == []
    assert database.coverage.count_documents({}) == 3
