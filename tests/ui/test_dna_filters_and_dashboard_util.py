"""High-yield coverage tests for blueprint filters and dashboard utilities."""

from __future__ import annotations

import importlib
from datetime import datetime

from flask import Flask


def _load_dna_filters():
    """Import DNA filter module under an active Flask app context."""
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test")
    with app.app_context():
        return importlib.import_module("coyote.blueprints.dna.filters")


def _load_dashboard_util():
    """Import dashboard utility module under an active Flask app context."""
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test")
    with app.app_context():
        module = importlib.import_module("coyote.blueprints.dashboard.util")
    return module.DashBoardUtility


def test_dashboard_utility_formats_stats_and_cache_key():
    """Cover dashboard formatting helpers."""
    DashBoardUtility = _load_dashboard_util()
    classified = [
        {"_id": {"assay": None, "nomenclature": "f", "class": 1}, "count": 10},
        {"_id": {"assay": None, "nomenclature": "g", "class": 2}, "count": 5},
        {"_id": {"assay": None, "nomenclature": "x", "class": 3}, "count": 1},
        {"_id": {"assay": "WGS", "nomenclature": "c", "class": 9}, "count": 99},
    ]
    class_stats = DashBoardUtility.format_classified_stats(classified)
    assert class_stats["fusion"][1] == 10
    assert class_stats["genomic"][2] == 5
    assert class_stats["no_nomenclature"][3] == 1
    assert "cnv" not in class_stats

    assay_classified = [
        {"_id": {"assay": "WGS", "nomenclature": "g", "class": 2}, "count": 7},
        {"_id": {"assay": None, "nomenclature": "p", "class": 4}, "count": 2},
        {"_id": {"assay": "RNA", "nomenclature": "f", "class": 1}, "count": 11},
    ]
    assay_stats = DashBoardUtility.format_assay_classified_stats(assay_classified)
    assert assay_stats["WGS"]["g"][2] == 7
    assert assay_stats["RNA"]["f"][1] == 11
    assert "NA" not in assay_stats

    asp_data = [
        {"_id": "A1", "asp_group": "dna", "count": 5},
        {"_id": "A2", "asp_group": "rna", "count": 3},
        {"_id": "A3", "count": 2},
    ]
    grouped = DashBoardUtility.format_asp_gene_stats(asp_data)
    assert len(grouped["dna"]) == 1
    assert len(grouped["rna"]) == 1
    assert len(grouped["Unknown"]) == 1

    key = DashBoardUtility.generate_dashboard_chache_key("user1", "all")
    assert key.startswith("dashboard:")
    assert len(key) > 20


def test_dna_blueprint_filter_helpers():
    """Cover common DNA blueprint template filters."""
    filters = _load_dna_filters()

    assert filters.has_hotspot_filter([{"hotspot": False}, {"hotspot": True}]) is True
    assert "SNV" in filters.format_panel_flag_snv("somatic:snv, somatic:cnv")
    assert "CNV" in filters.format_panel_flag_snv("somatic:snv, somatic:cnv")
    assert "2024-01-02" in filters.sortable_date(datetime(2024, 1, 2, 3, 4, 5))
    assert "NM_000546.(" in str(filters.standard_HGVS("NM_000546.5"))
    assert filters.perc_no_dec(0.252) == "25%"
    assert filters.perc_no_dec(None) is None
    assert filters.format_tier(1) == "Tier I"
    assert filters.format_tier("x") == "x"

    formatted = filters.format_filter(
        [
            "PASS",
            "WARN_HOMOPOLYMER",
            "WARN_PON_freebayes",
            "WARN_PON_vardict",
            "FAIL_PON_vardict",
            "WARN_NOVAR",
            "FAIL_CUSTOM",
        ]
    )
    assert "bg-pass" in formatted
    assert formatted.count("PON") == 2
    assert "FAIL_CUSTOM" in formatted

    assert filters.intersect([1, 2], [2, 3]) is True
    assert filters.unesc("a%2Fb") == "a/b"
    assert filters.format_fusion_desc("in-frame,driver")
    assert filters.uniq_callers([{"caller": "A"}, {"caller": "A"}, {"caller": "B"}]) == {"A", "B"}
    assert filters.basename("/tmp/file.txt") == "file.txt"
    assert filters.no_transid("GENE:NM_1") == "NM_1"
    assert filters.no_transid("GENE") is None
    assert "Malignt Melanom" in filters.format_hotspot_note(None)
    assert "bg-melanoma" in filters.format_hotspot(["mm_hotspot"])
    assert filters.one_letter_p("p.Gly12Asp") == "p.G12D"
    assert filters.ellipsify("abcdef", 3).endswith("...</span>")
    assert filters.multirow(["a", "b"]) == "a<br>b"
    assert filters.multirow("a&b") == "a<br>b"
    assert filters.round_to_3(0) == 0
    assert filters.format_gnomad("0.00123").endswith("%")
    assert filters.format_gnomad(None) == "-"
    assert filters.format_pop_freq("A:0.001&C:0.002", "C").endswith("%")
    assert filters.format_pop_freq("A:0.001", "G") == "N/A"
    assert filters.remove_prefix("PMID:1", "PMID:") == "1"
    assert "ncbi.nlm.nih.gov/pubmed/1" in filters.pubmed_links("PMID:1,PMID:2")
    assert filters.three_dec(0.1234)
    assert filters.three_dec(None) == ""
    assert filters.array_uniq([1, 1, 2]) == {1, 2}
    assert "<br />" in filters.format_oncokbtext("line1\nline2")
    assert filters.regex_replace("abc123", r"\d+", "") == "abc"
