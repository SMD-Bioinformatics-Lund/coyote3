"""Allowlisted clinical reporting facts."""

from __future__ import annotations

ALLOWED_FACT_PATHS: frozenset[str] = frozenset(
    {
        "sample.name",
        "sample.asp_id",
        "sample.subpanel_id",
        "sample.environment",
        "sample.omics_layer",
        "sample.analysis_intent",
        "sample.paired",
        "sample.genome_build",
        "asp.asp_id",
        "asp.asp_group",
        "asp.asp_category",
        "asp.accredited",
        "asp.germline_genes",
        "aspc.aspc_id",
        "aspc.asp_id",
        "aspc.asp_group",
        "aspc.asp_category",
        "aspc.subpanel_id",
        "aspc.environment",
        "aspc.reporting.analysis",
        "aspc.reporting.report_sections",
        "aspc.reporting.general_report_summary",
        "applied_gene_lists",
        "finding.kind",
        "finding.gene",
        "finding.genes",
        "finding.tier",
        "finding.exon",
        "finding.intron",
        "finding.case_vaf",
        "finding.case_vaf_percent",
        "finding.control_vaf",
        "finding.control_vaf_percent",
        "finding.consequence",
        "finding.hgvsc",
        "finding.hgvsp",
        "finding.variant_type",
        "finding.cnv_effect",
        "finding.fusion_gene_1",
        "finding.fusion_gene_2",
        "biomarkers",
        "aggregates.finding_count",
        "aggregates.snv_count",
        "aggregates.cnv_count",
        "aggregates.fusion_count",
        "aggregates.translocation_count",
        "aggregates.biomarker_count",
        "aggregates.tier_1_count",
        "aggregates.tier_2_count",
        "aggregates.tier_3_count",
        "aggregates.tier_summaries",
        "aggregates.has_tiered_snvs",
        "aggregates.has_reportable_findings",
    }
)


def validate_fact_path(path: str) -> None:
    """Reject facts that the prepared-context contract does not define."""
    if path not in ALLOWED_FACT_PATHS:
        raise ValueError(
            f"Unsupported clinical rule fact '{path}'. Add a typed prepared-context "
            "fact and tests before using it in a rule."
        )
