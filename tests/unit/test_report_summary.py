from __future__ import annotations

from types import SimpleNamespace

from api.core.interpretation import report_summary


def test_create_comment_doc_sample_specific_shape(monkeypatch):
    """Sample-specific comments are stored as direct comment entries."""
    monkeypatch.setattr(report_summary, "current_username", lambda: "tester")
    monkeypatch.setattr(report_summary, "utc_now", lambda: "2026-03-17T00:00:00Z")
    monkeypatch.setattr(
        report_summary,
        "_interpretation_repository",
        lambda: SimpleNamespace(new_comment_id=lambda: "cid-1"),
    )

    doc = report_summary.create_comment_doc({"text": "hello"})

    assert doc == {
        "_id": "cid-1",
        "hidden": 0,
        "text": "hello",
        "author": "tester",
        "time_created": "2026-03-17T00:00:00Z",
    }
