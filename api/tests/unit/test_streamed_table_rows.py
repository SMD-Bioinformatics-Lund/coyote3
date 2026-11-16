"""Streaming structural tables retain clinical search, ordering and count semantics."""

from coyote.application.common.table_state import select_table_rows


def test_deep_page_external_merge_preserves_ties_and_value_types(monkeypatch, tmp_path):
    import tempfile
    from datetime import datetime, timezone

    from bson import ObjectId
    from coyote_api.infra import external_sort

    monkeypatch.setattr(external_sort, "SORT_CHUNK_ROWS", 7)
    monkeypatch.setattr(external_sort, "MERGE_FAN_IN", 3)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    rows = [
        {"id": ObjectId(), "time": datetime.now(timezone.utc), "value": i % 13} for i in range(1500)
    ]
    expected = sorted(rows, key=lambda row: row["value"])[1200:1250]
    actual, metadata = select_table_rows(
        iter(rows),
        page_sorter=external_sort.sorted_page,
        search_query="",
        text_builder=str,
        specs=[("value", "asc")],
        value_getter=lambda row, field: row[field],
        page=25,
        per_page=50,
    )
    assert actual == expected
    assert metadata["total"] == 1500
    assert not list(tmp_path.iterdir())
