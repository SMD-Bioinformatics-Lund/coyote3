from __future__ import annotations

from dataclasses import dataclass

import pytest

from api.app.runtime_state import app
from api.app.utilities import assay_filters


@pytest.fixture(autouse=True)
def configured_runtime(monkeypatch):
    monkeypatch.setattr(
        app,
        "config",
        {
            "ASSAYS": {
                "hematology": {
                    "sample_info": ["case_id"],
                    "sample_qc": ["reads"],
                    "include_assays": ["hema_gmsv1"],
                    "subtypes": {"subtype_names": ["hem", "mpn"]},
                    "subtype_id_col": "subpanel_id",
                },
                "broken": {"subtypes": {"subtype_names": ["one"]}},
            },
            "GROUP_CONFIGS": {"hematology": {"label": "Hematology"}},
            "TABLE": {"page_size": 50},
            "CUTOFFS": {"hema_gmsv1": {"case": {"min_depth": 100}}},
            "PATH_ASSAY_CONFIG": "/config/assays.toml",
        },
    )


def test_runtime_configuration_accessors_return_copies_and_missing_defaults() -> None:
    assert assay_filters.assay_config() is not app.config["ASSAYS"]
    assert assay_filters.assay_config("hematology")["sample_info"] == ["case_id"]
    assert assay_filters.get_group_parameters("hematology") == {"label": "Hematology"}
    assert assay_filters.get_group_parameters("missing") is None
    assert assay_filters.table_config() == {"page_size": 50}
    assert assay_filters.cutoff_config("hema_gmsv1", "case") == {"min_depth": 100}
    assert assay_filters.cutoff_config("missing") == {}
    assert assay_filters.assay_info_vars("hematology") == ["case_id"]
    assert assay_filters.assay_qc_vars("hematology") == ["reads"]
    assert assay_filters.assays_in_assay_group("hematology") == ["hema_gmsv1"]
    assert assay_filters.has_subtypes("hematology") is True
    assert assay_filters.has_subtypes("missing") is False
    assert assay_filters.get_sample_subtypes("hematology") == ["hem", "mpn"]
    assert assay_filters.subtype_id_var("hematology") == "subpanel_id"
    assert assay_filters.subtype_id_var("missing") is None
    assert assay_filters.assay_exists("hematology") is True
    assert assay_filters.assay_exists("missing") is False
    assert assay_filters.assay_names_for_db_query("hematology") == ["hema_gmsv1"]
    assert assay_filters.assay_names_for_db_query("hematology_restored") == ["hema_gmsv1_restored"]


def test_runtime_configuration_accessors_handle_unconfigured_state(monkeypatch) -> None:
    monkeypatch.setattr(app, "config", {})
    assert assay_filters.assay_config() == {}
    assert assay_filters.get_group_parameters("x") == {}
    assert assay_filters.cutoff_config("x") == {}
    assert assay_filters.table_config() is None


def test_subtype_configuration_requires_identifier_column() -> None:
    with pytest.raises(AttributeError, match="subtype_id_col"):
        assay_filters.subtype_id_var("broken")


def test_fusion_settings_and_filter_gene_list_normalization() -> None:
    assert assay_filters.get_fusions_settings(
        {"filter_min_spanreads": "4"}, {"default_spanreads": 2, "default_spanpairs": 3}
    ) == {"min_spanreads": 4, "min_spanpairs": 3}
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
    assert assay_filters.get_case_and_control_sample_ids(
        {"case_id": "case", "control_id": "control"}
    ) == {"case": "case", "control": "control"}
    assert assay_filters.get_case_and_control_sample_ids({}) == {}
