from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import mongomock

from api.infra.mongo.repositories.samples import SampleRepository


def _handler_with_docs(*docs: dict) -> SampleRepository:
    client = mongomock.MongoClient()
    collection = client["coyote3_test"]["samples"]
    if docs:
        collection.insert_many(list(docs))
    adapter = SimpleNamespace(
        samples_collection=collection,
        app=SimpleNamespace(config={}, logger=SimpleNamespace(debug=lambda *a, **k: None)),
    )
    return SampleRepository(adapter)


def test_get_samples_returns_only_ready_docs() -> None:
    handler = _handler_with_docs(
        {
            "name": "ready-live",
            "asp_id": "ASP1",
            "environment": "production",
            "ingest_status": "ready",
            "report_num": 0,
        },
        {
            "name": "loading-live",
            "asp_id": "ASP1",
            "environment": "production",
            "ingest_status": "loading",
            "report_num": 0,
        },
        {
            "name": "failed-live",
            "asp_id": "ASP1",
            "environment": "production",
            "ingest_status": "failed",
            "report_num": 0,
        },
    )

    rows = handler.get_samples(
        user_assays=["ASP1"],
        user_envs=["production"],
        report=False,
        use_cache=False,
    )

    assert [row["name"] for row in rows] == ["ready-live"]


def test_get_samples_filters_by_added_utc_range() -> None:
    boundary = datetime(2026, 8, 19, 0, 0, tzinfo=timezone.utc)
    handler = _handler_with_docs(
        {
            "name": "before-range",
            "environment": "production",
            "ingest_status": "ready",
            "reported": False,
            "time_added": boundary - timedelta(seconds=1),
        },
        {
            "name": "inside-range",
            "environment": "production",
            "ingest_status": "ready",
            "reported": False,
            "time_added": boundary + timedelta(hours=2),
        },
        {
            "name": "at-exclusive-end",
            "environment": "production",
            "ingest_status": "ready",
            "reported": False,
            "time_added": boundary + timedelta(days=1),
        },
    )

    rows = handler.get_samples(
        user_assays=None,
        user_envs=["production"],
        report=False,
        added_from=boundary,
        added_until=boundary + timedelta(days=1),
        use_cache=False,
    )

    assert [row["name"] for row in rows] == ["inside-range"]


def test_search_samples_for_admin_returns_only_ready_docs_by_default() -> None:
    handler = _handler_with_docs(
        {
            "name": "ready-report",
            "asp_id": "ASP1",
            "environment": "production",
            "ingest_status": "ready",
            "report_num": 1,
        },
        {
            "name": "loading-report",
            "asp_id": "ASP1",
            "environment": "production",
            "ingest_status": "loading",
            "report_num": 1,
        },
    )

    rows, total = handler.search_samples_for_admin(
        asp_ids=["ASP1"], search_str="", page=1, per_page=30
    )

    assert total == 1
    assert [row["name"] for row in rows] == ["ready-report"]


def test_search_samples_for_admin_can_include_non_ready_docs() -> None:
    handler = _handler_with_docs(
        {
            "name": "ready-report",
            "asp_id": "ASP1",
            "environment": "production",
            "ingest_status": "ready",
            "report_num": 1,
        },
        {
            "name": "loading-report",
            "asp_id": "ASP1",
            "environment": "production",
            "ingest_status": "loading",
            "report_num": 1,
        },
    )

    rows, total = handler.search_samples_for_admin(
        asp_ids=["ASP1"],
        search_str="",
        page=1,
        per_page=30,
        ready_only=False,
    )

    assert total == 2
    assert [row["name"] for row in rows] == ["ready-report", "loading-report"]


def test_search_samples_for_admin_with_empty_assay_scope_returns_no_documents() -> None:
    handler = _handler_with_docs(
        {
            "name": "ready-report",
            "asp_id": "ASP1",
            "environment": "production",
            "ingest_status": "ready",
        }
    )

    rows, total = handler.search_samples_for_admin(
        asp_ids=[], search_str="", page=1, per_page=30, ready_only=False
    )

    assert rows == []
    assert total == 0
