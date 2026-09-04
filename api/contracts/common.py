"""Common route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CommonGeneInfoPayload(BaseModel):
    """Represent the common gene info payload."""

    gene: dict[str, Any] | None = None
    knowledgebase: dict[str, Any] = {}


class CommonTieredVariantContextPayload(BaseModel):
    """Represent the common tiered variant context payload."""

    variant: dict[str, Any]
    docs: list[dict[str, Any]]
    tier: int
    error: str | None = None


class CommonTieredVariantSearchPayload(BaseModel):
    """Represent the common tiered variant search payload."""

    docs: list[dict[str, Any]]
    search_str: str | None = None
    search_mode: str
    include_annotation_text: bool
    tier_stats: dict[str, Any]
    assays: list[str] | None = None
    assay_choices: list[str]
    nomenclatures: list[str] | None = None
    nomenclature_choices: list[str]


class GeneCohortBreakdown(BaseModel):
    """Represent a prevalence numerator and denominator."""

    profiled_samples: int
    finding_samples: int
    prevalence_percent: float | None = None


class GeneCohortSummary(GeneCohortBreakdown):
    """Represent top-level gene cohort counts."""

    reported_observations: int
    unique_findings: int


class GeneCohortDenominator(BaseModel):
    """Describe how the profiled-sample denominator was derived."""

    method: str
    report_scope: str
    ready_samples_considered: int
    samples_excluded_outside_gene_scope: int
    unrestricted_asp_scope_counts_as_profiled: bool
    duplicate_report_observations_removed: int = 0


class GeneCohortAssay(GeneCohortBreakdown):
    """Represent prevalence within one assay panel."""

    asp_id: str
    display_name: str
    asp_group: str | None = None


class GeneCohortSex(GeneCohortBreakdown):
    """Represent prevalence within one sample-level sex group."""

    sex: str


class GeneCohortFinding(BaseModel):
    """Represent one recurrent reported clinical-finding identity."""

    identity: str
    analysis_type: str
    nomenclature: str | None = None
    genes: list[str] = Field(default_factory=list)
    gene: str | None = None
    gene1: str | None = None
    gene2: str | None = None
    hgvsp: str | None = None
    hgvsc: str | None = None
    genomic: str | None = None
    transcript: str | None = None
    sample_count: int
    observation_count: int
    latest_tiers: list[int]
    historical_tiers: list[int]


class GeneCohortSampleFinding(BaseModel):
    """Represent one sample finding with its latest and historical tiers."""

    identity: str
    analysis_type: str
    nomenclature: str | None = None
    latest_tier: int
    tiers: list[int] = Field(default_factory=list)


class GeneCohortSample(BaseModel):
    """Represent a sample contributing a reported gene finding."""

    sample_name: str
    asp_id: str | None = None
    subpanel_id: str | None = None
    environment: str | None = None
    sex: str | None = None
    finding_details: list[GeneCohortSampleFinding] = Field(default_factory=list)


class CommonGeneCohortPayload(BaseModel):
    """Represent access-scoped cohort statistics for one gene."""

    query: dict[str, Any]
    gene: dict[str, Any] | None = None
    knowledgebase: dict[str, Any] = Field(default_factory=dict)
    summary: GeneCohortSummary
    denominator: GeneCohortDenominator
    tier_counts: dict[str, int]
    analysis_type_counts: dict[str, int] = Field(default_factory=dict)
    assays: list[GeneCohortAssay]
    sex_distribution: list[GeneCohortSex]
    recurrent_findings: list[GeneCohortFinding]
    samples: list[GeneCohortSample]
    truncated: bool = False


class KnowledgebaseGenePayload(BaseModel):
    """Represent aggregated gene-level knowledgebase context."""

    query: dict[str, Any]
    gene: dict[str, Any] | None = None
    sources: dict[str, Any] = {}
    available_sources: list[str] = []


class KnowledgebaseSummaryDatum(BaseModel):
    """Represent one named count in a knowledgebase summary."""

    name: str
    value: int


class CancerGeneCensusSummaryPayload(BaseModel):
    """Represent non-clinical aggregate Cancer Gene Census information."""

    available: bool
    total_genes: int = 0
    tiers: list[KnowledgebaseSummaryDatum] = Field(default_factory=list)
    origins: list[KnowledgebaseSummaryDatum] = Field(default_factory=list)
    roles: list[KnowledgebaseSummaryDatum] = Field(default_factory=list)
    mutation_types: list[KnowledgebaseSummaryDatum] = Field(default_factory=list)
    molecular_genetics: list[KnowledgebaseSummaryDatum] = Field(default_factory=list)
    hallmarks: list[KnowledgebaseSummaryDatum] = Field(default_factory=list)
    hallmark_records: int = 0


class KnowledgebaseSourceStatisticsPayload(BaseModel):
    """Represent aggregate, non-clinical statistics for one reference source."""

    key: str
    name: str
    available: bool
    total: int = 0
    unit: str = "records"
    distribution: list[KnowledgebaseSummaryDatum] = Field(default_factory=list)
    metrics: list[KnowledgebaseSummaryDatum] = Field(default_factory=list)


class KnowledgebaseStatisticsPayload(BaseModel):
    """Represent aggregate statistics for configured knowledgebase sources."""

    sources: list[KnowledgebaseSourceStatisticsPayload] = Field(default_factory=list)


class KnowledgebaseVariantPayload(BaseModel):
    """Represent aggregated variant-level knowledgebase context."""

    query: dict[str, Any]
    variant: dict[str, Any]
    sources: dict[str, Any] = {}
    available_sources: list[str] = []
