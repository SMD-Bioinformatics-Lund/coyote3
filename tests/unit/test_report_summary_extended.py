from __future__ import annotations

import pytest

from api.application.interpretation import report_summary


def _snv(gene: str, tier: int, af: float, *, irrelevant: bool = False) -> dict:
    return {
        "GT": [{"type": "case", "AF": af}],
        "INFO": {"selected_CSQ": {"SYMBOL": gene}},
        "classification": {"class": tier},
        "irrelevant": irrelevant,
    }


def test_process_annotations_groups_class_and_text_by_required_context() -> None:
    grouped = report_summary.process_gene_annotations(
        [
            {"class": 1, "assay": "hema", "subpanel": "hem", "variant": "v1"},
            {"text": "one", "assay": "hema", "subpanel": "hem", "variant": "v1"},
            {"class": 2, "assay": "solid", "subpanel": "colon", "variant": "v2"},
            {"text": "two", "assay": "solid", "subpanel": "colon", "variant": "v2"},
        ]
    )
    assert grouped["hema:hem"]["v1"]["latest_class"]["class"] == 1
    assert grouped["hema:hem"]["v1"]["latest_text"]["text"] == "one"
    assert grouped["solid:colon"]["v2"]["latest_class"]["class"] == 2
    assert grouped["solid:colon"]["v2"]["latest_text"]["text"] == "two"


def test_process_annotations_rejects_rows_without_required_context() -> None:
    with pytest.raises(KeyError, match="assay"):
        report_summary.process_gene_annotations([{"class": 2, "variant": "v2"}])


def test_global_structural_comment_shapes(monkeypatch) -> None:
    monkeypatch.setattr(report_summary, "current_username", lambda: "tester")
    monkeypatch.setattr(report_summary, "utc_now", lambda: "now")
    fusion = report_summary.create_comment_doc(
        {
            "global": "global",
            "comment": "fusion",
            "gene1": "KMT2A",
            "gene2": "AFF1",
        },
        nomenclature="f",
        variant="KMT2A_AFF1",
        key="comment",
    )
    cnv = report_summary.create_comment_doc(
        {"global": "global", "text": "gain", "gene": "EGFR"},
        nomenclature="cn",
        variant="7_gain",
    )
    assert fusion["gene1"] == "KMT2A" and fusion["gene2"] == "AFF1"
    assert "gene" not in fusion and "gene" not in cnv
    assert "transcript" not in cnv


def test_intro_covers_paired_lists_gene_counts_and_germline_scope() -> None:
    intro = report_summary.summarize_intro(
        ["case", "control"],
        ["CEBPA"],
        ["hem"],
        {"reporting": {"general_report_summary": "Baseline. "}},
        {"germline_genes": ["CEBPA"]},
    )
    assert "hudbiopsi" in intro
    assert "genlistan: HEM" in intro
    assert "genen: CEBPA" in intro
    assert "konstitutionella mutationer" in intro

    large = report_summary.summarize_intro(
        ["case"],
        [f"G{i}" for i in range(21)],
        ["one", "two"],
        {"reporting": {}},
        {},
    )
    assert "genlistorna" in large and "21 gener" in large
    assert "hudbiopsi" not in large


def test_tier_sort_and_summary_cover_filters_single_and_multiple_genes() -> None:
    variants = [
        _snv("TP53", 1, 0.4),
        _snv("TP53", 1, 0.2),
        _snv("NPM1", 2, 0.3),
        _snv("FLT3", 3, 0.1),
        _snv("DROP", 1, 0.9, irrelevant=True),
        _snv("OUTSIDE", 2, 0.8),
    ]
    grouped, counts = report_summary.sort_tiered_variants(variants, ["TP53", "NPM1", "FLT3"])
    text = report_summary.summarize_tiered_snvs(grouped, counts, "")
    assert counts == {1: 2, 2: 1, 3: 1}
    assert "två mutationer" in text
    assert "Vidare ses" in text
    assert "Slutligen ses" in text
    assert "TP53" in text and "NPM1" in text and "FLT3" in text

    multiple = report_summary.summarize_tiered_snvs(
        {1: {"TP53": ["20%"], "NPM1": ["30%"]}}, {1: 2}, ""
    )
    assert "TP53" in multiple and "NPM1" in multiple


def test_translocation_summary_covers_mane_ann_read_types_and_unique_reads() -> None:
    variants = [
        {
            "interesting": True,
            "INFO": {
                "MANE_ANN": {"Gene_Name": "KMT2A&AFF1"},
                "UR": 12,
            },
            "GT": [{"PR": "90,10", "SR": "80,20"}],
        },
        {
            "interesting": True,
            "INFO": {"ANN": [{"Gene_Name": "RUNX1&RUNX1T1"}]},
            "GT": [{"SR": "50,50"}],
        },
        {
            "interesting": True,
            "INFO": {"ANN": [{"Gene_Name": "PML&RARA"}], "UR": 8},
            "GT": [{"PR": "75,25"}],
        },
        {"interesting": False, "INFO": {"ANN": [{"Gene_Name": "NO&NO"}]}, "GT": []},
    ]
    text = report_summary.summarize_transloc(variants)
    assert "KMT2A och AFF1" in text
    assert "överspännande läsningar" in text
    assert "splittade läsningar" in text
    assert "12 unika läsningar" in text
    assert "Slutligen" in text


def test_cnv_summary_covers_depth_and_structural_callers() -> None:
    variants = [
        {
            "interesting": True,
            "chr": "7",
            "start": 1,
            "end": 2,
            "ratio": 1.0,
            "genes": [{"gene": "EGFR", "class": 1}, {"gene": "OTHER"}],
            "callers": ["cnvkit"],
            "SR": 0,
            "PR": 0,
        },
        {
            "interesting": True,
            "chr": "9",
            "start": 3,
            "end": 4,
            "ratio": -1.0,
            "genes": [{"gene": "CDKN2A", "class": 2}, {"gene": "CDKN2B", "class": 2}],
            "callers": ["manta"],
            "SR": "80/20",
            "PR": "90/10",
        },
        {
            "interesting": True,
            "chr": "1",
            "start": 5,
            "end": 6,
            "ratio": 0.5,
            "genes": [{"gene": "MYCL", "class": 3}],
            "callers": ["gatk"],
            "SR": 0,
            "PR": 0,
        },
        {"interesting": False},
    ]
    text = report_summary.summarize_cnv(variants)
    assert "amplifiering" in text and "förlust" in text
    assert "EGFR" in text and "CDKN2A" in text and "CDKN2B" in text
    assert "överspännande läsningar" in text and "splittade läsningar" in text
    assert "Slutligen" in text


def test_biomarker_summary_and_percentage_invalid_values() -> None:
    text = report_summary.summarize_bio(
        [
            {"HRD": {"sum": 50}, "MSIP": {"per": 20}, "MSIS": {"per": 30}},
            {"MSIP": {"per": 2}, "MSIS": {"per": 18}},
        ]
    )
    assert "positivt HRD-värde" in text
    assert "20.0%" in text and "18.0%" in text
    assert report_summary._biomarker_percentage(None) == 0
    assert report_summary._biomarker_percentage({"per": "invalid"}) == 0


def test_generate_summary_text_builds_all_sections_and_accreditation() -> None:
    summary = report_summary.generate_summary_text(
        ["case"],
        {"reporting": {"general_report_summary": "Intro. "}},
        {"accredited": False, "germline_genes": []},
        {
            "snvs": [_snv("TP53", 1, 0.2)],
            "cnvs": [
                {
                    "interesting": True,
                    "chr": "7",
                    "start": 1,
                    "end": 2,
                    "ratio": 1.0,
                    "genes": [{"gene": "EGFR", "class": 1}],
                    "callers": ["cnvkit"],
                    "SR": 0,
                    "PR": 0,
                }
            ],
            "translocs": [],
            "fusions": [],
            "biomarkers": [{"MSIP": {"per": 16}}],
        },
        ["TP53"],
        [],
    )
    assert "Kliniskt relevanta SNVs" in summary
    assert "kopietalsförändringar" in summary
    assert "Andra kliniskt relevanta biomarkörer" in summary
    assert "omfattas inte av ackrediteringen" in summary

    no_findings = report_summary.generate_summary_text(
        ["case"],
        {"reporting": {}},
        {"accredited": True},
        {"snvs": []},
        [],
        [],
    )
    assert "inga somatiskt förvärvade mutationer" in no_findings
    assert "omfattas inte" not in no_findings


def test_tier_classification_uses_last_selected_tier_and_defaults_zero() -> None:
    assert report_summary.get_tier_classification({}) == 0
    assert report_summary.get_tier_classification({"tier1": True, "tier4": False}) == 4


def test_enrichment_empty_and_missing_related_documents() -> None:
    class EmptySamples:
        def get_samples_by_oids(self, _oids):
            return [None]

    class EmptyAnnotations:
        def get_annotations_by_oids(self, _oids):
            return [None]

    assert (
        report_summary.enrich_reported_variant_docs(
            [], sample_repository=EmptySamples(), annotation_repository=EmptyAnnotations()
        )
        == []
    )
    enriched = report_summary.enrich_reported_variant_docs(
        [{"tier": 1}],
        sample_repository=EmptySamples(),
        annotation_repository=EmptyAnnotations(),
    )
    assert enriched[0]["sample"]["sample_name"] is None
    assert enriched[0]["annotation"] == {}
