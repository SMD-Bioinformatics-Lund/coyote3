"""Report ordering preserves unavailable structural-variant allele fractions."""

from coyote3.application.reporting.dna_report_payload import (
    get_simple_variants_for_report,
    sort_by_class_and_af,
)


def test_report_rows_order_tiers_then_numeric_af_without_changing_display_values():
    rows = [
        {"class": 2, "af": 0.9},
        {"class": 1, "af": "N/A"},
        {"class": 1, "af": 0.1},
        {"class": 1, "af": None},
        {"class": 1, "af": 0.5},
        {"class": 1, "af": 0},
    ]
    assert sort_by_class_and_af(rows) == [rows[i] for i in [4, 2, 5, 1, 3, 0]]
    assert rows[1]["af"] == "N/A"
    assert rows[3]["af"] is None


def test_tiered_flt3_structural_finding_can_be_sorted_for_report_preview():
    finding = {
        "CHROM": "13",
        "POS": 100,
        "REF": "A",
        "ALT": "AT",
        "INFO": {"SVTYPE": "INS", "SVLEN": 1, "selected_CSQ": {"SYMBOL": "FLT3"}},
        "classification": {"class": 1},
        "GT": [{"type": "case", "AF": 0.25}],
    }
    rows = get_simple_variants_for_report([finding], {})
    assert rows[0]["af"] == "N/A"
    assert sort_by_class_and_af(rows) == rows
