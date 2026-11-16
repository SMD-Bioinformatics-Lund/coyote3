"""Streaming structural tables retain clinical search, ordering and count semantics."""

import random

import pytest
from coyote.application.common.pagination import paginate_items
from coyote.application.common.table_state import search_items, select_table_rows, sort_items


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
