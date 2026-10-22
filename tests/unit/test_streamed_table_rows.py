"""Streaming structural tables retain clinical search, ordering and count semantics."""

import random

import pytest

from api.application.common.pagination import paginate_items
from api.application.common.table_state import search_items, select_table_rows, sort_items


def test_deep_page_external_merge_preserves_ties_and_value_types(monkeypatch, tmp_path):
    import tempfile
    from datetime import datetime, timezone

    from bson import ObjectId

    from api.infra import external_sort

    monkeypatch.setattr(external_sort, "SORT_CHUNK_ROWS", 7)
    monkeypatch.setattr(external_sort, "MERGE_FAN_IN", 3)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    rows = [
        {"id": ObjectId(), "time": datetime.now(timezone.utc), "value": i % 13} for i in range(1500)
    ]
    expected = sorted(rows, key=lambda row: row["value"])[1200:1250]
    actual, metadata = select_table_rows(
        iter(rows),
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


@pytest.mark.parametrize("page", [None, 1, 2, 8, 100])
@pytest.mark.parametrize("query", ["", "tp53", "tp53 loss", "absent"])
@pytest.mark.parametrize("specs", [[], [("score", "asc")], [("score", "desc"), ("text", "asc")]])
def test_streamed_pages_match_established_table_behavior(page, query, specs):
    """Mixed missing values, ties and out-of-range pages preserve exact results."""
    rng = random.Random(7)
    rows = [
        {
            "id": index,
            "score": rng.choice([None, 0, 1, 2]),
            "text": rng.choice(["TP53 loss", "BCR fusion", "TP53 gain"]),
        }
        for index in range(350)
    ]

    def getter(row, field):
        """Read the selected sort value without coercing missing values."""
        return row[field]

    def text(row):
        """Use the same searchable text for both implementations."""
        return row["text"]

    expected = sort_items(
        search_items(rows, search_query=query, text_builder=text), specs=specs, value_getter=getter
    )
    selected, metadata = select_table_rows(
        iter(rows),
        search_query=query,
        text_builder=text,
        specs=specs,
        value_getter=getter,
        page=page,
        per_page=25,
    )
    if page is None:
        assert selected == expected
        assert metadata["total"] == len(expected)
        assert not metadata["has_next"]
    else:
        expected_rows, expected_metadata = paginate_items(expected, page=page, per_page=25)
        assert selected == expected_rows
        assert metadata == expected_metadata
