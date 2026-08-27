from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import mongomock
from bson import ObjectId

from api.infra.mongo.repositories.samples import SampleRepository
from api.infra.mongo.repositories.variants import VariantsRepository


class _Cache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: object, timeout: int = 0) -> None:
        _ = timeout
        self.values[key] = value


def _adapter():
    db = mongomock.MongoClient()["coyote3_test"]
    app = SimpleNamespace(
        config={"CACHE_DEFAULT_TIMEOUT": 60},
        cache=_Cache(),
        logger=logging.getLogger("repository-test"),
        home_logger=logging.getLogger("repository-test"),
    )
    return SimpleNamespace(
        app=app,
        coyote_db=db,
        samples_collection=db["samples"],
        variants_collection=db["variants"],
    )


def test_sample_repository_indexes_pagination_sorting_and_literal_search() -> None:
    adapter = _adapter()
    repository = SampleRepository(adapter)
    repository.ensure_indexes()
    now = datetime.now(timezone.utc)
    adapter.samples_collection.insert_many(
        [
            {
                "name": "CASE[1]",
                "asp_id": "panel_a",
                "environment": "production",
                "ingest_status": "ready",
                "reported": False,
                "time_added": now - timedelta(hours=2),
            },
            {
                "name": "CASE.2",
                "case": {"clarity_id": "MATCHING_CLARITY"},
                "asp_id": "panel_a",
                "environment": "production",
                "ingest_status": "ready",
                "reported": False,
                "time_added": now,
            },
            {
                "name": "OTHER",
                "asp_id": "panel_b",
                "environment": "testing",
                "ingest_status": "ready",
                "reported": True,
                "time_added": now + timedelta(hours=1),
                "latest_report_on": now - timedelta(days=1),
            },
            {
                "name": "REPORTED_RECENTLY",
                "asp_id": "panel_b",
                "environment": "testing",
                "ingest_status": "ready",
                "reported": True,
                "time_added": now - timedelta(days=30),
                "latest_report_on": now,
            },
        ]
    )

    page = repository.get_samples(
        ["panel_a"],
        ["production"],
        limit=1,
        offset=1,
        use_cache=False,
    )
    literal = repository.get_samples(
        None,
        None,
        search_str="[1]",
        use_cache=False,
    )
    matching_page = repository.get_samples_page(
        user_assays=["panel_a"],
        user_envs=["production"],
        status="live",
        report=False,
        search_str="case",
        sort="sample:asc",
        limit=1,
        offset=1,
    )
    clarity_match = repository.get_samples_page(
        user_assays=None,
        user_envs=None,
        status="live",
        report=False,
        search_str="matching_clarity",
        sort="",
        limit=50,
    )
    reported_default = repository.get_samples_page(
        user_assays=None,
        user_envs=None,
        status="done",
        report=True,
        search_str="",
        sort="",
        limit=50,
    )
    reported_added = repository.get_samples_page(
        user_assays=None,
        user_envs=None,
        status="done",
        report=True,
        search_str="",
        sort="added:desc",
        limit=50,
    )

    assert [row["name"] for row in page] == ["CASE[1]"]
    assert [row["name"] for row in literal] == ["CASE[1]"]
    assert matching_page["total"] == 2
    assert [row["name"] for row in matching_page["items"]] == ["CASE[1]"]
    assert [row["name"] for row in clarity_match["items"]] == ["CASE.2"]
    assert [row["name"] for row in reported_default["items"]] == [
        "REPORTED_RECENTLY",
        "OTHER",
    ]
    assert [row["name"] for row in reported_added["items"]] == [
        "OTHER",
        "REPORTED_RECENTLY",
    ]
    indexes = adapter.samples_collection.index_information()
    assert "name_1" in indexes
    assert "ingest_status_1_omics_layer_1_asp_id_1_environment_1" in indexes
    assert "reported_1_latest_report_on_-1" in indexes


def test_sample_repository_update_and_missing_document_semantics(monkeypatch) -> None:
    adapter = _adapter()
    repository = SampleRepository(adapter)
    sample_id = adapter.samples_collection.insert_one({"name": "CASE_A"}).inserted_id
    monkeypatch.setattr(
        "api.infra.mongo.repositories.samples.invalidate_samples_cache", lambda *_: None
    )
    monkeypatch.setattr(
        "api.infra.mongo.repositories.base.invalidate_dashboard_summary_cache", lambda *_: None
    )

    result = repository.update_sample(sample_id, {"name": "CASE_A", "reported": True})

    assert result.matched_count == 1
    assert repository.get_sample_by_id(str(sample_id))["reported"] is True
    assert repository.get_sample_by_id(str(ObjectId())) is None
    assert repository.get_sample_by_id("invalid-object-id") is None


def test_variant_repository_indexes_exact_identity_and_missing_document() -> None:
    adapter = _adapter()
    repository = VariantsRepository(adapter)
    repository.ensure_indexes()
    variant_id = adapter.variants_collection.insert_one(
        {
            "simple_id": "7_140453136_A_T",
            "simple_id_hash": "different-untrusted-hash",
            "SAMPLE_ID": "sample-1",
        }
    ).inserted_id

    assert repository.get_variant(str(variant_id))["SAMPLE_ID"] == "sample-1"
    assert repository.get_variant(str(ObjectId())) is None
    assert "sample_id_1" in adapter.variants_collection.index_information()
    identity = repository._simple_id_identity_query("7_140453136_A_T")
    assert identity["simple_id"] == "7_140453136_A_T"
    assert len(identity["simple_id_hash"]) == 32
