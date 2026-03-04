"""UI polish checks for sortable-table arrows."""

from __future__ import annotations


def test_sort_arrows_are_hidden_by_default_and_sized():
    script_path = "coyote/static/js/sortableTable.js"
    with open(script_path, encoding="utf-8") as handle:
        script = handle.read()

    assert "sort-arrow hidden" in script
    assert "w-3 text-[10px] leading-none" in script
    assert "aria-hidden" in script
