"""Tests for canonical server-side table state parsing."""

from api.application.common.table_state import (
    numeric_value,
    parse_sort_specs,
    search_items,
    sort_items,
    sort_spec_to_query_value,
    sortable_text,
)


def test_parse_sort_specs_accepts_ordered_multi_column_sort_state() -> None:
    """The canonical sort query preserves each field and direction."""
    assert parse_sort_specs({"sort": "case_vaf:desc,gene:asc"}) == [
        ("case_vaf", "desc"),
        ("gene", "asc"),
    ]


def test_parse_sort_specs_ignores_retired_single_column_parameters() -> None:
    """The API no longer accepts the retired sort_by/sort_dir pair."""
    assert parse_sort_specs({"sort_by": "case_vaf", "sort_dir": "desc"}) == []


def test_table_state_normalizes_values_and_ignores_empty_sort_tokens() -> None:
    """Malformed or empty client sort tokens cannot alter the table query state."""
    specs = parse_sort_specs({"sort": " gene:DESC, ,tier:sideways,:desc"})

    assert specs == [("gene", "desc"), ("tier", "asc")]
    assert sort_spec_to_query_value(specs) == "gene:desc,tier:asc"
    assert numeric_value(True) == 1.0
    assert numeric_value("3.5") == 3.5
    assert numeric_value("not-a-number") is None
    assert sortable_text("Tp53") == "tp53"
    assert sortable_text("") is None


def test_table_state_searches_all_terms_and_sorts_complete_result_set() -> None:
    """Multi-column sorting is global and missing values remain at the end."""
    rows = [
        {"gene": "TP53", "vaf": 0.12},
        {"gene": "KRAS", "vaf": 0.70},
        {"gene": "TP53", "vaf": None},
    ]
    filtered = search_items(rows, search_query="tp53", text_builder=lambda row: row["gene"])
    ordered = sort_items(
        filtered,
        specs=[("vaf", "desc"), ("gene", "asc")],
        value_getter=lambda row, field: row.get(field),
    )

    assert ordered == [
        {"gene": "TP53", "vaf": 0.12},
        {"gene": "TP53", "vaf": None},
    ]
