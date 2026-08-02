"""Prepared, query-free facts consumed by clinical reporting rules."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _FactModel(BaseModel):
    """Strict base for data exposed to clinical rules."""

    model_config = ConfigDict(extra="forbid")


class PreparedSampleFacts(_FactModel):
    """Stable sample facts available to reporting rules."""

    name: str
    asp_id: str
    subpanel_id: str
    environment: str
    omics_layer: Literal["dna", "rna"]
    paired: bool = False
    genome_build: int | str | None = None
    analysis_intent: Literal["somatic", "germline"] = "somatic"


class PreparedAspFacts(_FactModel):
    """Stable physical-assay facts available to reporting rules."""

    asp_id: str
    asp_group: str | None = None
    asp_category: str | None = None
    accredited: bool = False
    germline_genes: list[str] = Field(default_factory=list)


class PreparedAspcReportingFacts(_FactModel):
    """Stable ASPC reporting facts."""

    report_sections: list[str] = Field(default_factory=list)
    general_report_summary: str = ""


class PreparedAspcFacts(_FactModel):
    """Stable analytical-configuration facts available to rules."""

    aspc_id: str
    asp_id: str
    asp_group: str | None = None
    asp_category: str | None = None
    subpanel_id: str
    environment: str
    reporting: PreparedAspcReportingFacts = Field(default_factory=PreparedAspcReportingFacts)


class PreparedGeneListFacts(_FactModel):
    """One exact ISGL selected during report preparation."""

    isgl_id: str
    version: int | str | None = None
    list_type: list[str] = Field(default_factory=list)
    selected_for: list[str] = Field(default_factory=list)
    genes: list[str] = Field(default_factory=list)
    germline_genes: list[str] = Field(default_factory=list)
    adhoc: bool = False


class PreparedFindingFacts(_FactModel):
    """One already filtered and classified report candidate."""

    kind: Literal["snv", "cnv", "fusion", "translocation"]
    gene: str | None = None
    genes: list[str] = Field(default_factory=list)
    tier: int | None = None
    exon: list[str] = Field(default_factory=list)
    intron: list[str] = Field(default_factory=list)
    case_vaf: float | None = None
    case_vaf_percent: float | None = None
    control_vaf: float | None = None
    control_vaf_percent: float | None = None
    consequence: list[str] = Field(default_factory=list)
    hgvsc: str | None = None
    hgvsp: str | None = None
    variant_type: str | None = None
    cnv_effect: str | None = None
    fusion_gene_1: str | None = None
    fusion_gene_2: str | None = None


class PreparedTierGeneFacts(_FactModel):
    """One gene and its ordered case-VAF labels within a tier."""

    gene: str
    vaf_percentages: list[str] = Field(default_factory=list)


class PreparedTierSummaryFacts(_FactModel):
    """Ordered reportable SNVs grouped by clinical tier and gene."""

    tier: int
    finding_count: int
    genes: list[PreparedTierGeneFacts] = Field(default_factory=list)


class PreparedAggregateFacts(_FactModel):
    """Deterministic counts derived from the prepared findings."""

    finding_count: int = 0
    snv_count: int = 0
    cnv_count: int = 0
    fusion_count: int = 0
    translocation_count: int = 0
    biomarker_count: int = 0
    tier_1_count: int = 0
    tier_2_count: int = 0
    tier_3_count: int = 0
    tier_summaries: list[PreparedTierSummaryFacts] = Field(default_factory=list)
    has_tiered_snvs: bool = False
    has_reportable_findings: bool = False


class PreparedReportContext(BaseModel):
    """Complete deterministic input to one rule evaluation.

    This object is assembled by the reporting workflow after filtering and
    classification. The evaluator never queries persistence or mutates it.
    """

    model_config = ConfigDict(extra="forbid")

    sample: PreparedSampleFacts
    asp: PreparedAspFacts
    aspc: PreparedAspcFacts
    applied_gene_lists: list[PreparedGeneListFacts] = Field(default_factory=list)
    findings: list[PreparedFindingFacts] = Field(default_factory=list)
    biomarkers: list[dict[str, Any]] = Field(default_factory=list)
    aggregates: PreparedAggregateFacts = Field(default_factory=PreparedAggregateFacts)

    def evaluation_scope(self, finding: PreparedFindingFacts | None = None) -> dict[str, Any]:
        """Return the allowlisted root objects exposed to rules and templates."""
        return {
            "sample": self.sample.model_dump(mode="python"),
            "asp": self.asp.model_dump(mode="python"),
            "aspc": self.aspc.model_dump(mode="python"),
            "applied_gene_lists": [
                gene_list.model_dump(mode="python") for gene_list in self.applied_gene_lists
            ],
            "finding": finding.model_dump(mode="python") if finding else {},
            "biomarkers": self.biomarkers,
            "aggregates": self.aggregates.model_dump(mode="python"),
        }
