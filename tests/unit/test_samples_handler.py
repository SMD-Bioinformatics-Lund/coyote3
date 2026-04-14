from __future__ import annotations

from types import SimpleNamespace

import mongomock

from api.infra.mongo.handlers.samples import SampleHandler


def _handler_with_docs(*docs: dict) -> SampleHandler:
    client = mongomock.MongoClient()
    collection = client["coyote3_test"]["samples"]
    if docs:
        collection.insert_many(list(docs))
    adapter = SimpleNamespace(
        samples_collection=collection,
        app=SimpleNamespace(config={}, logger=SimpleNamespace(debug=lambda *a, **k: None)),
    )
    return SampleHandler(adapter)


def test_get_samples_returns_only_ready_docs() -> None:
    handler = _handler_with_docs(
        {
            "name": "ready-live",
            "assay": "ASP1",
            "profile": "production",
            "ingest_status": "ready",
            "report_num": 0,
        },
        {
            "name": "loading-live",
            "assay": "ASP1",
            "profile": "production",
            "ingest_status": "loading",
            "report_num": 0,
        },
        {
            "name": "failed-live",
            "assay": "ASP1",
            "profile": "production",
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


def test_search_samples_for_admin_returns_only_ready_docs_by_default() -> None:
    handler = _handler_with_docs(
        {
            "name": "ready-report",
            "assay": "ASP1",
            "profile": "production",
            "ingest_status": "ready",
            "report_num": 1,
        },
        {
            "name": "loading-report",
            "assay": "ASP1",
            "profile": "production",
            "ingest_status": "loading",
            "report_num": 1,
        },
    )

    rows, total = handler.search_samples_for_admin(
        assays=["ASP1"], search_str="", page=1, per_page=30
    )

    assert total == 1
    assert [row["name"] for row in rows] == ["ready-report"]


def test_search_samples_for_admin_can_include_non_ready_docs() -> None:
    handler = _handler_with_docs(
        {
            "name": "ready-report",
            "assay": "ASP1",
            "profile": "production",
            "ingest_status": "ready",
            "report_num": 1,
        },
        {
            "name": "loading-report",
            "assay": "ASP1",
            "profile": "production",
            "ingest_status": "loading",
            "report_num": 1,
        },
    )

    rows, total = handler.search_samples_for_admin(
        assays=["ASP1"],
        search_str="",
        page=1,
        per_page=30,
        ready_only=False,
    )

    assert total == 2
    assert [row["name"] for row in rows] == ["ready-report", "loading-report"]
