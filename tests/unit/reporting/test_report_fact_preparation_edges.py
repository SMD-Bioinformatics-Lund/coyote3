"""Edge coverage for deterministic clinical-report fact preparation."""

from api.application.reporting.clinical_rules.preparation import prepare_report_context


def test_prepare_report_context_normalizes_every_supported_finding_family() -> None:
    context = prepare_report_context(
        sample={
            "name": "synthetic-case",
            "asp_id": "hema_gmsv1",
            "paired": True,
            "genome_build": 38,
        },
        asp={
            "asp_group": "hematology",
            "asp_category": "panel",
            "accredited": True,
            "germline_genes": ["TP53"],
        },
        aspc={
            "aspc_id": "hema_gmsv1_base_production",
            "asp_id": "hema_gmsv1",
            "subpanel_id": "base",
            "environment": "production",
            "reporting": {
                "analysis": ["SNV", "CNV", "FUSION", "BIOMARKER"],
                "report_sections": ["results"],
                "general_report_summary": "Configured summary.",
            },
        },
        analyte="dna",
        intent="germline",
        applied_gene_lists=[
            {
                "isgl_id": "synthetic_list",
                "version": 2,
                "list_type": "snv",
                "selected_for": ["snv"],
                "genes": ["TP53"],
                "germline_genes": ["TP53"],
                "adhoc": 1,
            }
        ],
        report_sections_data={
            "snvs": [
                {
                    "INFO": {
                        "selected_CSQ": {
                            "SYMBOL": "TP53",
                            "Consequence": "missense_variant&splice_region_variant",
                            "EXON": "4/11",
                            "INTRON": "5/10",
                            "HGVSc": "NM_000546.6:c.215C>G",
                            "HGVSp": "NP_000537.3:p.Pro72Arg",
                        }
                    },
                    "GT": [
                        {"type": "case", "AF": "0.125"},
                        {"type": "control", "AF": "invalid"},
                    ],
                    "classification": {"class": 2},
                    "variant_class": "SNV",
                },
                {
                    "symbol": "KRAS",
                    "consequence": ["missense_variant"],
                    "exon": ["2"],
                    "af": "0.2",
                    "class": 1,
                    "cdna": "NM_004985.5:c.35G>A",
                    "variant": "NP_004976.2:p.Gly12Asp",
                    "var_type": "SNV",
                },
            ],
            "cnvs": [
                {
                    "genes": [{"gene": "EGFR"}, "invalid", {}],
                    "ratio": 1.2,
                    "classification": {"class": 2},
                },
                {
                    "genes": [{"gene": "CDKN2A"}, {"gene": "MTAP"}],
                    "ratio": -1,
                },
            ],
            "fusions": [{"gene1": "BCR", "gene2": "ABL1", "classification": {"class": 1}}],
            "translocs": [{"INFO": {"ANN": [{"Gene_Name": "ETV6&RUNX1"}]}}],
            "biomarkers": [{"name": "MSI", "value": "stable"}],
        },
    )

    assert context.sample.subpanel_id == "base"
    assert context.sample.environment == "production"
    assert context.sample.analysis_intent == "germline"
    assert context.asp.asp_id == "hema_gmsv1"
    assert context.aspc.reporting.analysis == ["SNV", "CNV", "FUSION", "BIOMARKER"]
    assert context.applied_gene_lists[0].list_type == ["snv"]
    assert context.applied_gene_lists[0].adhoc is True

    tp53, kras, gain, loss, fusion, translocation = context.findings
    assert tp53.gene == "TP53"
    assert tp53.consequence == ["missense_variant", "splice_region_variant"]
    assert tp53.exon == ["4"]
    assert tp53.intron == ["5"]
    assert tp53.case_vaf_percent == 12.5
    assert tp53.control_vaf is None
    assert kras.gene == "KRAS"
    assert kras.case_vaf == 0.2
    assert kras.hgvsc == "NM_004985.5:c.35G>A"
    assert gain.gene == "EGFR"
    assert gain.cnv_effect == "gain"
    assert loss.gene is None
    assert loss.genes == ["CDKN2A", "MTAP"]
    assert loss.cnv_effect == "loss"
    assert fusion.genes == ["BCR", "ABL1"]
    assert fusion.fusion_gene_1 == "BCR"
    assert translocation.genes == ["ETV6", "RUNX1"]

    assert context.aggregates.finding_count == 6
    assert context.aggregates.biomarker_count == 1
    assert context.aggregates.tier_2_count == 1
    assert context.aggregates.tier_1_count == 0
    assert context.aggregates.has_tiered_snvs is True
    assert context.aggregates.has_reportable_findings is True


def test_tier_summaries_skip_irrelevant_invalid_and_unselected_findings() -> None:
    context = prepare_report_context(
        sample={"name": "synthetic-case", "asp_id": "assay"},
        asp={},
        aspc={},
        analyte="dna",
        applied_gene_lists=[],
        report_sections_data={
            "snvs": [
                {
                    "INFO": {"selected_CSQ": {"SYMBOL": "SKIP1"}},
                    "classification": {"class": 1},
                    "irrelevant": True,
                    "af": 0.9,
                },
                {
                    "INFO": {"selected_CSQ": {"SYMBOL": "SKIP2"}},
                    "classification": {"class": 4},
                    "af": 0.8,
                },
                {"symbol": "SKIP3", "classification": {"class": 2}, "af": 0.7},
                {
                    "INFO": {"selected_CSQ": {"SYMBOL": "KEEP"}},
                    "classification": {"class": 3},
                    "GT": [{"type": "case", "AF": None}],
                },
            ]
        },
    )

    assert context.sample.subpanel_id == "base"
    assert context.sample.environment == ""
    assert context.aspc.asp_id == "assay"
    assert context.aggregates.tier_1_count == 0
    assert context.aggregates.tier_2_count == 0
    assert context.aggregates.tier_3_count == 1
    assert context.aggregates.tier_summaries[0].genes[0].vaf_percentages == [""]


def test_empty_report_context_has_no_reportable_findings() -> None:
    context = prepare_report_context(
        sample={"name": "synthetic-case"},
        asp={},
        aspc={},
        analyte="rna",
        applied_gene_lists=[],
        report_sections_data={},
    )

    assert context.sample.omics_layer == "rna"
    assert context.findings == []
    assert context.biomarkers == []
    assert context.aggregates.finding_count == 0
    assert context.aggregates.has_tiered_snvs is False
    assert context.aggregates.has_reportable_findings is False
