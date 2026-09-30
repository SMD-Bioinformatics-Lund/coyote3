"""Coverage for supported domain filter formatting and sample identifiers."""

from __future__ import annotations

from dataclasses import dataclass

from api.app.utilities.assay_filters import get_case_and_control_sample_ids
from api.domain.common import assay_filters


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
    assert broad["focus"]["covered"] == ["KRAS", "TP53"]
    assert broad["focus"]["uncovered"] == []
    assert assay_filters.get_assay_genelist_names([{"_id": "one"}, {"_id": "two"}]) == [
        "one",
        "two",
    ]


def test_format_assay_config_supports_list_schema_defaults_and_preserves_extensions() -> None:
    config = {
        "min_depth": 90,
        "filters": {"min_vaf": 0.03, "extension": "kept", "_id": "remove"},
        "reporting": {"report_sections": ["SNV"], "extension": True, "id": "remove"},
        "display_name": "Production",
    }
    schema = {
        "sections": {
            "filters": [
                "min_depth",
                {"key": "min_vaf", "default": 0.01},
                {"name": "max_vaf", "default": 1.0},
                {"default": "ignored"},
                "filters",
            ],
            "reporting": [
                {"field": "report_sections", "default": []},
                {"id": "include_snapshot", "default": False},
                "reporting",
            ],
        }
    }
    formatted = assay_filters.format_assay_config(config, schema)
    assert formatted["display_name"] == "Production"
    assert formatted["filters"] == {
        "min_depth": 90,
        "min_vaf": 0.03,
        "max_vaf": 1.0,
        "extension": "kept",
    }
    assert formatted["reporting"] == {
        "report_sections": ["SNV"],
        "include_snapshot": False,
        "extension": True,
    }


def test_format_assay_config_handles_none_and_non_mapping_sections() -> None:
    assert assay_filters.format_assay_config(None, None) == {"filters": {}, "reporting": {}}
    formatted = assay_filters.format_assay_config(
        {"filters": "invalid", "reporting": []},
        {"sections": {"filters": {"min_depth": {"default": 10}}, "reporting": {}}},
    )
    assert formatted == {"filters": {"min_depth": 10}, "reporting": {}}


@dataclass
class _Field:
    name: str
    data: object


def test_format_filters_from_form_supports_iterable_and_mapping_schemas() -> None:
    form = [
        _Field("vep_missense_variant", True),
        _Field("snvlist_heme", "on"),
        _Field("fusionlist_mitelman", 1),
        _Field("fusioncaller_arriba", True),
        _Field("fusioneffect_in_frame", True),
        _Field("cnveffect_gain", True),
        _Field("min_depth", 100),
    ]
    schema = {
        "sections": {
            "filters": [
                "vep_consequences",
                {"key": "snvlists"},
                {"id": "fusionlists"},
                {"name": "fusion_callers"},
                {"field": "fusion_effects"},
                "cnveffects",
                "min_depth",
                {"default": 1},
            ]
        }
    }
    assert assay_filters.format_filters_from_form(form, schema) == {
        "vep_consequences": ["missense_variant"],
        "snvlists": ["heme"],
        "fusionlists": ["mitelman"],
        "fusion_callers": ["arriba"],
        "fusion_effects": ["in_frame"],
        "cnveffects": ["gain"],
        "min_depth": 100,
    }
    assert assay_filters.format_filters_from_form(
        {"min_depth": 50}, {"sections": {"filters": {"min_depth": {}}}}
    ) == {"min_depth": 50}


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
