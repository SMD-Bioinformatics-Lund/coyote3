"""Tests for canonical server-side table state parsing."""

from api.application.common.table_state import parse_sort_specs


def test_parse_sort_specs_accepts_ordered_multi_column_sort_state() -> None:
    """The canonical sort query preserves each field and direction."""
    assert parse_sort_specs({"sort": "case_vaf:desc,gene:asc"}) == [
        ("case_vaf", "desc"),
        ("gene", "asc"),
    ]


def test_parse_sort_specs_ignores_retired_single_column_parameters() -> None:
    """The API no longer accepts the retired sort_by/sort_dir pair."""
    assert parse_sort_specs({"sort_by": "case_vaf", "sort_dir": "desc"}) == []
