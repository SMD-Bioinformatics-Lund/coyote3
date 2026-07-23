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
    assay: str
    subpanel_id: str
    profile: str
    omics_layer: Literal["dna", "rna"]
    paired: bool = False
    genome_build: int | str | None = None


class PreparedAspFacts(_FactModel):
    """Stable physical-assay facts available to reporting rules."""

    asp_id: str
    asp_group: str | None = None
    asp_category: str | None = None
    accredited: bool = False


class PreparedAspcReportingFacts(_FactModel):
    """Stable ASPC reporting facts."""

    analysis: list[str] = Field(default_factory=list)
    report_sections: list[str] = Field(default_factory=list)


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
