"""Coverage for supported domain filter formatting and sample identifiers."""

from __future__ import annotations

from coyote.domain.common import assay_filters
from coyote.domain.common.assay_filters import get_case_and_control_sample_ids


def test_filter_gene_list_normalization() -> None:
    genes = assay_filters.create_filter_genelist(
        {
            "one": {"is_active": True, "covered": ["TP53", "EGFR"]},
            "two": {"is_active": True, "covered": ["TP53"]},
            "off": {"is_active": False, "covered": ["KRAS"]},
        }
    )
    assert sorted(genes) == ["EGFR", "TP53"]


def test_panel_and_broad_assay_gene_coverage() -> None:
    panel = assay_filters.get_genes_covered_in_panel(
        {"focus": {"genes": ["TP53", "KRAS"]}},
        {"covered_genes": ["TP53", "EGFR"], "asp_family": "panel-dna"},
    )
    assert panel["focus"]["covered"] == ["TP53"]
    assert panel["focus"]["uncovered"] == ["KRAS"]

    broad = assay_filters.get_genes_covered_in_panel(
        {"focus": {"genes": ["TP53", "KRAS"]}},
        {"covered_genes": [], "asp_family": "wgs"},
    )
    assert broad["focus"]["covered"] == []
    assert broad["focus"]["uncovered"] == ["KRAS", "TP53"]
    assert assay_filters.get_assay_genelist_names([{"_id": "one"}, {"_id": "two"}]) == [
        "one",
        "two",
    ]


def test_group_map_and_case_control_identifiers() -> None:
    grouped = assay_filters.create_assay_group_map(
        [
            {
                "asp_group": "solid",
                "asp_id": "solid_one",
                "display_name": "Solid one",
                "asp_category": "dna",
            },
            {
                "asp_group": "solid",
                "asp_id": "solid_two",
                "display_name": "Solid two",
                "asp_category": "rna",
            },
        ]
    )
    assert [row["asp_id"] for row in grouped["solid"]] == ["solid_one", "solid_two"]
    assert get_case_and_control_sample_ids({"case_id": "case", "control_id": "control"}) == {
        "case": "case",
        "control": "control",
    }
    assert get_case_and_control_sample_ids({}) == {}
