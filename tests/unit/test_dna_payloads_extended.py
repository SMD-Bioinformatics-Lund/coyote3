"""Extended behavioral tests for DNA route payload construction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.application.dna import payloads
from api.domain.core.exceptions import AppError


def _selected_variant(**overrides):
    variant = {
        "_id": "variant-1",
        "SAMPLE_ID": "sample-1",
        "CHROM": "17",
        "POS": 10,
        "REF": "C",
        "ALT": "T",
        "variant_class": "SNV",
        "simple_id_hash": "hash-1",
        "FILTER": ["PASS", "PON"],
        "GT": [
            {"sample": "case", "type": "case", "AF": "0.25", "VD": 5, "DP": 20},
            {"sample": "control", "type": "control", "AF": 0.01, "VD": 1, "DP": 100},
        ],
        "INFO": {
            "SVLEN": 1,
            "selected_CSQ": {
                "SYMBOL": "TP53",
                "HGNC_ID": "HGNC:11998",
                "Gene": "ENSG1",
                "Feature": "NM_000546.6",
                "HGVSc": "c.1C>T",
                "HGVSp": "p.Arg1Cys",
                "EXON": "2/11",
                "INTRON": "-",
                "Consequence": ["missense_variant", "splice_region_variant"],
            },
        },
        "gnomad_frequency": "0.001",
        "classification": {"class": 2},
        "transcripts": ["NM_000546.6"],
    }
    variant.update(overrides)
    return variant


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("", None), (True, 1.0), ("2.5", 2.5), ("bad", None)],
)
def test_numeric_value(value, expected) -> None:
    assert payloads._numeric_value(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2/11", (0, 2, 11)),
        ("3", (0, 3, 0)),
        ("unknown", (1, 0, "unknown")),
        ("-", None),
    ],
)
def test_sortable_fraction(value, expected) -> None:
    assert payloads._sortable_fraction(value) == expected


@pytest.mark.parametrize(
    ("chromosome", "expected"),
    [("chr2", (0, 2)), ("X", (0, 23)), ("MT", (0, 25)), ("GL1", (1, "GL1")), (None, None)],
)
def test_chromosome_sort_value(chromosome, expected) -> None:
    assert payloads._chromosome_sort_value(chromosome) == expected


def test_variant_sort_values_cover_supported_columns() -> None:
    variant = _selected_variant()
    assert payloads._variant_sort_value(variant, "gene") == "tp53"
    assert payloads._variant_sort_value(variant, "hgvs") == "c.1c>t p.arg1cys"
    assert payloads._variant_sort_value(variant, "exon") == (0, 2, 11)
    assert payloads._variant_sort_value(variant, "type") == "snv"
    assert payloads._variant_sort_value(variant, "indel_size") == 1.0
    assert payloads._variant_sort_value(variant, "consequence") == (
        "missense_variant, splice_region_variant"
    )
    assert payloads._variant_sort_value(variant, "popfreq") == 0.001
    assert payloads._variant_sort_value(variant, "hotspot") == 0
    assert payloads._variant_sort_value(variant, "tier") == 2.0
    assert payloads._variant_sort_value(variant, "chrpos") == ((0, 17), 10.0)
    assert payloads._variant_sort_value(variant, "flags") == "pass, pon"
    assert payloads._variant_sort_value(variant, "case_vaf") == 0.25
    assert payloads._variant_sort_value(variant, "control_vaf") == 0.01
    assert payloads._variant_sort_value(variant, "unsupported") is None


def test_variant_hotspot_sort_value_matches_displayed_hotspot_state() -> None:
    variant = _selected_variant(hotspots=[{"lu": ["COSV66102297"]}])
    assert payloads._variant_sort_value(variant, "hotspot") == 1

    hydrated = _selected_variant()
    hydrated["INFO"]["HOTSPOT"] = ["co"]
    assert payloads._variant_sort_value(hydrated, "hotspot") == 1


def test_variant_sort_handles_scalar_consequence_filter_and_tier() -> None:
    variant = _selected_variant(FILTER="WARN", tier="3")
    variant.pop("classification")
    variant["INFO"]["selected_CSQ"]["Consequence"] = "intron_variant&NMD_transcript_variant"
    assert payloads._variant_sort_value(variant, "consequence") == (
        "intron_variant, nmd_transcript_variant"
    )
    assert payloads._variant_sort_value(variant, "flags") == "warn"
    assert payloads._variant_sort_value(variant, "tier") == 3.0


def test_search_matches_all_terms_across_variant_fields() -> None:
    tp53 = _selected_variant()
    npm1 = _selected_variant(_id="variant-2", CHROM="5", FILTER="PASS")
    npm1["INFO"]["selected_CSQ"] = {
        "SYMBOL": "NPM1",
        "HGVSc": "c.860_863dup",
        "HGVSp": "p.Trp288fs",
        "Consequence": "frameshift_variant",
    }
    assert payloads._search_variants([tp53, npm1], "TP53 0.25") == [tp53]
    assert payloads._search_variants([tp53, npm1], "frameshift") == [npm1]
    assert payloads._search_variants([tp53], "") == [tp53]


def test_analysis_section_normalization_is_stable() -> None:
    assert payloads._normalize_dna_analysis_sections(
        ["snv", "TMB", "PGX", "biomarker", "SNV", "cnv", ""]
    ) == ["SNV", "CNV", "BIOMARKER"]


def test_gene_enrichment_collectors_handle_configured_and_missing_repositories() -> None:
    variants = [_selected_variant()]
    service = SimpleNamespace(
        oncokb_public_cache_repository=SimpleNamespace(
            get_gene_records=lambda genes: {gene: {"gene": gene} for gene in genes}
        ),
        oncokb_repository=SimpleNamespace(
            get_oncokb_action_gene_records=lambda genes: {
                gene: {"actionable": True} for gene in genes
            }
        ),
        clinpgx_public_repository=SimpleNamespace(
            get_gene_records=lambda genes: {gene: {"pgx": True} for gene in genes}
        ),
    )
    assert payloads._collect_oncokb_genes(service, variants) == ["TP53"]
    assert payloads._collect_oncokb_gene_map(service, ["TP53"])["TP53"]["gene"] == "TP53"
    assert payloads._collect_oncokb_actionable_gene_map(service, ["TP53"])["TP53"] == {
        "actionable": True
    }
    assert payloads._collect_clinpgx_gene_map(service, ["TP53"])["TP53"] == {"pgx": True}
    empty = SimpleNamespace(
        oncokb_public_cache_repository=SimpleNamespace(),
        oncokb_repository=SimpleNamespace(),
        clinpgx_public_repository=SimpleNamespace(),
    )
    assert payloads._collect_oncokb_gene_map(empty, ["TP53"]) == {}
    assert payloads._collect_oncokb_actionable_gene_map(empty, []) == {}
    assert payloads._collect_clinpgx_gene_map(empty, []) == {}


def test_display_and_summary_sections_load_each_enabled_analysis(monkeypatch) -> None:
    monkeypatch.setattr(
        payloads,
        "build_transloc_query",
        lambda sample_id, settings: {"sample_id": sample_id, "settings": settings},
    )
    monkeypatch.setattr(
        payloads,
        "filter_translocations_by_genes",
        lambda rows, **kwargs: [{**row, "restricted": kwargs["restricted"]} for row in rows],
    )
    service = SimpleNamespace(
        load_cnvs_for_sample=lambda **kwargs: [
            {"_id": "cnv-interesting", "interesting": True},
            {"_id": "cnv-other", "interesting": False},
        ],
        biomarker_repository=SimpleNamespace(
            get_sample_biomarkers=lambda sample_id: [{"_id": "tmb", "sample": sample_id}]
        ),
        translocation_repository=SimpleNamespace(
            get_sample_translocations=lambda query: [
                {"_id": "transloc-1", "interesting": True, "query": query}
            ]
        ),
    )
    display, summary = payloads._build_display_and_summary_sections(
        service,
        variants=[{"_id": "snv-1"}],
        tiered_variants=[{"_id": "snv-tiered"}],
        analysis_sections=["CNV", "BIOMARKER", "TRANSLOCATION", "FUSION"],
        sample={"_id": "sample-1"},
        sample_filters={},
        cnv_filters={"gain": 3},
        filter_genes=["TP53"],
        cnv_filter_genes=["MYC"],
        translocation_filter_genes=["NTRK1"],
        translocation_restricted=True,
        assay_group="solid",
    )
    assert display["snvs"] == [{"_id": "snv-1"}]
    assert summary["snvs"] == [{"_id": "snv-tiered"}]
    assert summary["cnvs"] == [{"_id": "cnv-interesting", "interesting": True}]
    assert display["biomarkers"][0]["sample"] == "sample-1"
    assert display["translocs"][0]["restricted"] is True
    assert display["fusions"] == []
    assert summary["translocs"][0]["_id"] == "transloc-1"


def test_plot_and_biomarker_payloads_and_missing_configuration() -> None:
    sample = {"_id": "sample-1", "name": "SAMPLE_1"}
    service = SimpleNamespace(
        biomarker_repository=SimpleNamespace(
            get_sample_biomarkers=lambda sample_id: [{"sample": sample_id}]
        )
    )
    plot = payloads.plot_context_payload(
        service=service,
        sample=sample,
        assay_config_getter=lambda value: {"reporting": {"plots_path": "/plots"}},
    )
    assert plot["plots_base_dir"] == "/plots"
    biomarkers = payloads.biomarkers_payload(service=service, sample=sample)
    assert biomarkers["meta"]["count"] == 1
    with pytest.raises(AppError) as exc:
        payloads.plot_context_payload(
            service=service, sample=sample, assay_config_getter=lambda value: None
        )
    assert exc.value.status_code == 422


def _context_service(variant):
    return SimpleNamespace(
        variant_repository=SimpleNamespace(
            get_variant=lambda variant_id: variant,
            get_variant_in_other_samples=lambda row: [{"sample": "other"}],
            hidden_var_comments=lambda variant_id: True,
        ),
        blacklist_repository=SimpleNamespace(add_blacklist_data=lambda rows, group: rows),
        annotation_repository=SimpleNamespace(
            get_global_annotations=lambda row, group, subpanel: (
                [{"text": "annotation"}],
                {"class": 2},
                [{"class": 3}],
                True,
            )
        ),
        expression_repository=SimpleNamespace(get_expression_data=lambda transcripts: transcripts),
        anno_vep_repository=SimpleNamespace(
            get_for_variant=lambda **kwargs: {"CSQ": [{"Feature": "NM_000546.6"}, "bad"]}
        ),
        civic_repository=SimpleNamespace(
            get_civic_data=lambda row, desc: {"description": desc},
            get_civic_gene_info=lambda gene: {"gene": gene},
        ),
        oncokb_repository=SimpleNamespace(
            get_oncokb_anno=lambda row, candidates: candidates,
            get_oncokb_action=lambda row, candidates: [{"candidate": candidates[0]}],
            get_oncokb_gene=lambda gene: {"local": gene},
        ),
        oncokb_public_cache_repository=SimpleNamespace(
            get_gene_record=lambda gene: {"public": gene}
        ),
        clinpgx_public_repository=SimpleNamespace(get_gene_record=lambda gene: {"pgx": gene}),
        brca_repository=SimpleNamespace(get_brca_data=lambda row, group: {"group": group}),
        iarc_tp53_repository=SimpleNamespace(find_iarc_tp53=lambda row: {"found": True}),
        bam_record_repository=SimpleNamespace(get_bams=lambda ids: ids),
        vep_metadata_repository=SimpleNamespace(
            get_variant_class_translations=lambda version: {"version": version},
            get_conseq_translations=lambda version: {"version": version},
        ),
        assay_panel_repository=SimpleNamespace(get_asp_group_mappings=lambda: {"solid": []}),
    )


def test_variant_context_rejects_missing_foreign_and_configuration_errors() -> None:
    sample = {"_id": "sample-1", "name": "SAMPLE_1", "database_versions": {"vep": "110"}}
    for variant, config in ((None, {}), (_selected_variant(SAMPLE_ID="other"), {})):
        with pytest.raises(AppError) as exc:
            payloads.variant_context_payload(
                service=_context_service(variant),
                sample=sample,
                var_id="variant-1",
                add_alt_class_fn=lambda *args: args[0],
                util_module=SimpleNamespace(),
                assay_config_getter=lambda value: config,
            )
        assert exc.value.status_code == 404
    with pytest.raises(AppError) as exc:
        payloads.variant_context_payload(
            service=_context_service(_selected_variant()),
            sample=sample,
            var_id="variant-1",
            add_alt_class_fn=lambda *args: args[0],
            util_module=SimpleNamespace(),
            assay_config_getter=lambda value: None,
        )
    assert exc.value.status_code == 422


def test_variant_context_builds_transcript_and_knowledgebase_payload() -> None:
    variant = _selected_variant()
    sample = {
        "_id": "sample-1",
        "name": "SAMPLE_1",
        "asp_id": "solid_gmsv3",
        "subpanel_id": "colon",
        "database_versions": {"vep": "110"},
    }
    observed = payloads.variant_context_payload(
        service=_context_service(variant),
        sample=sample,
        var_id="variant-1",
        add_alt_class_fn=lambda row, group, subpanel: {**row, "alternative": True},
        util_module=SimpleNamespace(
            common=SimpleNamespace(get_case_and_control_sample_ids=lambda value: {"case": "C1"})
        ),
        assay_config_getter=lambda value: {"asp_group": "solid"},
    )
    assert observed["sample_summary"]["name"] == "SAMPLE_1"
    assert observed["transcripts"] == [{"Feature": "NM_000546.6"}]
    assert observed["latest_classification"]["class"] == 2
    assert observed["oncokb_gene"] == {"public": "TP53"}
    assert observed["clinpgx_gene"] == {"pgx": "TP53"}
    assert observed["civic"]["description"] == "NOTHING_IN_HERE"
    assert observed["bam_id"] == {"case": "C1"}


def test_variant_context_derives_transcript_badges_from_current_hgnc() -> None:
    variant = _selected_variant()
    sample = {
        "_id": "sample-1",
        "name": "SAMPLE_1",
        "asp_id": "solid_gmsv3",
        "subpanel_id": "colon",
        "database_versions": {"vep": "110"},
    }
    service = _context_service(variant)
    service.anno_vep_repository = SimpleNamespace(
        get_for_variant=lambda **kwargs: {
            "CSQ": [
                {
                    "Feature": "NM_000546.6",
                    "HGNC_ID": "HGNC:11998",
                    "SYMBOL": "TP53",
                }
            ]
        }
    )
    service.hgnc_repository = SimpleNamespace(
        get_metadata_by_ids_and_symbols=lambda _ids, _symbols: [
            {
                "hgnc_id": "HGNC:11998",
                "hgnc_symbol": "TP53",
                "refseq_mane_plus_clinical": ["NM_000546.6"],
            }
        ]
    )

    observed = payloads.variant_context_payload(
        service=service,
        sample=sample,
        var_id="variant-1",
        add_alt_class_fn=lambda row, group, subpanel: row,
        util_module=SimpleNamespace(
            common=SimpleNamespace(get_case_and_control_sample_ids=lambda value: {"case": "C1"})
        ),
        assay_config_getter=lambda value: {"asp_group": "solid"},
    )

    transcript = observed["transcripts"][0]
    assert transcript["transcript_tags"] == ["ncbi_mane_plus_clinical"]
    assert transcript["canonical_source"] is None
    assert transcript["is_canonical"] is False
    assert "HGNC_MATCHED" not in transcript
    assert "VEP_SYMBOL" not in transcript


@pytest.mark.parametrize(
    ("symbol", "consequence", "info", "expected"),
    [
        ("CALR", ["frameshift_variant"], {}, "EXON 9 FRAMESHIFT"),
        ("FLT3", ["inframe_insertion"], {"SVLEN": 12}, "ITD"),
    ],
)
def test_variant_context_sets_special_clinical_descriptions(
    symbol, consequence, info, expected
) -> None:
    variant = _selected_variant(
        INFO={
            "SVLEN": info.get("SVLEN", 1),
            "selected_CSQ": {
                "SYMBOL": symbol,
                "EXON": "9/9",
                "Feature": "NM_1",
                "HGVSp": "p.Arg1fs",
                "Consequence": consequence,
            },
        }
    )
    sample = {"_id": "sample-1", "database_versions": {"vep": "110"}}
    observed = payloads.variant_context_payload(
        service=_context_service(variant),
        sample=sample,
        var_id="variant-1",
        add_alt_class_fn=lambda row, group, subpanel: row,
        util_module=SimpleNamespace(
            common=SimpleNamespace(get_case_and_control_sample_ids=lambda value: {})
        ),
        assay_config_getter=lambda value: {"asp_group": "hematology"},
    )
    assert observed["civic"]["description"] == expected
