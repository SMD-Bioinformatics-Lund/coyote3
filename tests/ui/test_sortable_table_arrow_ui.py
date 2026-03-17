"""UI polish checks for sortable-table arrows."""

from __future__ import annotations


def test_sort_arrows_are_hidden_by_default_and_sized():
    """Handle test sort arrows are hidden by default and sized.

    Returns:
        The function result.
    """
    script_path = "coyote/static/js/sortableTable.js"
    with open(script_path, encoding="utf-8") as handle:
        script = handle.read()

    assert "sort-arrow hidden" in script
    assert "h-2 w-2 items-center justify-center text-[7px] leading-[1]" in script
    assert "aria-hidden" in script


def test_case_frequency_column_defaults_to_descending_sort():
    """Handle test case frequency column defaults to descending sort.

    Returns:
        The function result.
    """
    template_path = "coyote/blueprints/dna/templates/list_dna_findings.html"
    with open(template_path, encoding="utf-8") as handle:
        template = handle.read()

    assert 'data-autoclick="true" data-default-order="desc"' in template
