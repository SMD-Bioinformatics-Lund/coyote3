"""Unit tests for DNA payload builders."""

from __future__ import annotations

from types import SimpleNamespace

from api.services.dna import payloads
from tests.fixtures.api import mock_collections as fx


def test_list_variants_payload_sorts_main_variant_table_by_case_af_desc() -> None:
    """The main SNV/INDEL table should arrive pre-sorted by case AF descending."""
    sample = fx.sample_doc()
    assay_config = {
        "asp_group": "tumwgs",
        "analysis_types": [],
        "reporting": {},
    }
    variants = [
        {"_id": "low", "GT": [{"type": "case", "AF": 0.12}]},
        {"_id": "high", "GT": [{"type": "case", "AF": 0.89}]},
        {"_id": "mid", "GT": [{"type": "case", "AF": 0.34}]},
    ]

    service = SimpleNamespace(
        assay_panel_handler=SimpleNamespace(get_asp=lambda asp_name: {"asp_name": asp_name}),
        gene_list_handler=SimpleNamespace(
            get_isgl_by_ids=lambda ids: {},
            get_isgl_by_asp=lambda assay, is_active=True: [],
        ),
        variant_handler=SimpleNamespace(get_case_variants=lambda query: variants),
        blacklist_handler=SimpleNamespace(add_blacklist_data=lambda rows, assay_group: rows),
        bam_record_handler=SimpleNamespace(get_bams=lambda sample_ids: {}),
        vep_metadata_handler=SimpleNamespace(
            get_variant_class_translations=lambda vep: {},
            get_conseq_translations=lambda vep: {},
        ),
        sample_handler=SimpleNamespace(hidden_sample_comments=lambda sample_oid: False),
        oncokb_handler=SimpleNamespace(get_oncokb_action_gene=lambda symbol: None),
    )
    util_module = SimpleNamespace(
        common=SimpleNamespace(
            merge_sample_settings_with_assay_config=lambda s, a: s,
            get_sample_effective_genes=lambda s, a, g, target="snv": ({}, []),
            get_case_and_control_sample_ids=lambda s: {"case": "C1"},
            get_assay_genelist_names=lambda docs: [],
        )
    )

    payload = payloads.list_variants_payload(
        service=service,
        request=SimpleNamespace(url=SimpleNamespace(path="/api/v1/samples/S1/small-variants")),
        sample=sample,
        util_module=util_module,
        add_global_annotations_fn=lambda rows, assay_group, subpanel: (rows, []),
        generate_summary_text_fn=lambda *args, **kwargs: "",
        build_query_fn=lambda assay_group, params: {"assay_group": assay_group, **params},
        get_filter_conseq_terms_fn=lambda values: [],
        assay_config_getter=lambda _sample: assay_config,
    )

    assert [variant["_id"] for variant in payload["variants"]] == ["high", "mid", "low"]
    assert [variant["_id"] for variant in payload["display_sections_data"]["snvs"]] == [
        "high",
        "mid",
        "low",
    ]


def test_list_variants_payload_maps_tmb_and_pgx_to_biomarker_section() -> None:
    """TMB/PGX toggles should surface the shared biomarker findings section."""
    sample = fx.sample_doc()
    assay_config = {
        "asp_group": "panel",
        "analysis_types": ["SNV", "TMB", "PGX"],
        "reporting": {},
    }

    service = SimpleNamespace(
        assay_panel_handler=SimpleNamespace(get_asp=lambda asp_name: {"asp_name": asp_name}),
        gene_list_handler=SimpleNamespace(
            get_isgl_by_ids=lambda ids: {},
            get_isgl_by_asp=lambda assay, is_active=True: [],
        ),
        variant_handler=SimpleNamespace(get_case_variants=lambda query: []),
        blacklist_handler=SimpleNamespace(add_blacklist_data=lambda rows, assay_group: rows),
        bam_record_handler=SimpleNamespace(get_bams=lambda sample_ids: {}),
        vep_metadata_handler=SimpleNamespace(
            get_variant_class_translations=lambda vep: {},
            get_conseq_translations=lambda vep: {},
        ),
        sample_handler=SimpleNamespace(hidden_sample_comments=lambda sample_oid: False),
        oncokb_handler=SimpleNamespace(get_oncokb_action_gene=lambda symbol: None),
        biomarker_handler=SimpleNamespace(
            get_sample_biomarkers=lambda sample_id: [{"name": "TMB", "value": "High"}]
        ),
        load_cnvs_for_sample=lambda **kwargs: [],
        translocation_handler=SimpleNamespace(get_sample_translocations=lambda query: []),
    )
    util_module = SimpleNamespace(
        common=SimpleNamespace(
            merge_sample_settings_with_assay_config=lambda s, a: s,
            get_sample_effective_genes=lambda s, a, g, target="snv": ({}, []),
            get_case_and_control_sample_ids=lambda s: {"case": "C1"},
            get_assay_genelist_names=lambda docs: [],
        )
    )

    payload = payloads.list_variants_payload(
        service=service,
        request=SimpleNamespace(url=SimpleNamespace(path="/api/v1/samples/S1/small-variants")),
        sample=sample,
        util_module=util_module,
        add_global_annotations_fn=lambda rows, assay_group, subpanel: (rows, []),
        generate_summary_text_fn=lambda *args, **kwargs: "",
        build_query_fn=lambda assay_group, params: {"assay_group": assay_group, **params},
        get_filter_conseq_terms_fn=lambda values: [],
        assay_config_getter=lambda _sample: assay_config,
    )

    assert payload["analysis_sections"] == ["SNV", "BIOMARKER"]
    assert payload["display_sections_data"]["biomarkers"][0]["name"] == "TMB"
