"""Core MongoDB document models for Coyote3 collections.

These contracts model common/critical keys for each collection while keeping
``extra="allow"`` for forward compatibility.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, TypeAdapter, field_validator


class _DocBase(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class VersionHistoryEntryDoc(_DocBase):
    version: int | float | None = None
    user: str | None = None
    date: str | None = None
    diff: dict[str, Any] | None = None
    delta: dict[str, Any] | None = None
    initial: bool | None = None


class SampleCaseControlDoc(_DocBase):
    id: str | None = None
    clarity_id: str | None = None
    clarity_pool_id: str | None = None
    ffpe: bool | str | None = None
    sequencing_run: str | None = None
    reads: int | float | None = None
    purity: float | str | None = None


class SampleCommentDoc(_DocBase):
    author: str
    text: str
    hidden: int | bool | None = None
    hidden_by: str | None = None
    time_created: Any | None = None
    time_hidden: Any | None = None


class SampleReportDoc(_DocBase):
    author: str | None = None
    filepath: str | None = None
    report_id: str | None = None
    report_name: str | None = None
    report_num: int | None = None
    report_type: str | None = None
    time_created: Any | None = None


class SampleFiltersDoc(_DocBase):
    max_freq: float | int | None = None
    min_freq: float | int | None = None
    min_depth: int | None = None
    min_alt_reads: int | None = None
    max_control_freq: float | int | None = None
    max_popfreq: float | int | None = None
    min_cnv_size: int | None = None
    max_cnv_size: int | None = None
    cnv_loss_cutoff: float | int | None = None
    cnv_gain_cutoff: float | int | None = None
    warn_cov: int | None = None
    error_cov: int | None = None
    vep_consequences: list[str] = Field(default_factory=list)
    cnveffects: list[str] = Field(default_factory=list)
    genelists: list[str] = Field(default_factory=list)


class VariantCsqDoc(_DocBase):
    """Common CSQ transcript entry used inside variant INFO."""

    Feature: str | None = None
    HGNC_ID: str | None = None
    SYMBOL: str | None = None
    PolyPhen: str | None = None
    SIFT: str | None = None
    Consequence: str | list[str] | None = None
    IMPACT: str | None = None
    VARIANT_CLASS: str | None = None
    HGVSc: str | None = None
    HGVSp: str | None = None
    BIOTYPE: str | None = None
    CANONICAL: str | None = None
    MANE: str | None = None


class VariantInfoDoc(_DocBase):
    """Typed INFO payload for variants with permissive extension keys."""

    variant_callers: list[str] | str = Field(default_factory=list)
    PON_NUM_tnscope: str | None = None
    PON_VAFS_tnscope: str | None = None
    CSQ: list[VariantCsqDoc] = Field(
        validation_alias=AliasChoices("CSQ", "csq"),
        default_factory=list,
    )
    selected_CSQ: VariantCsqDoc | None = Field(
        validation_alias=AliasChoices("selected_CSQ", "selectedCSQ"),
        default=None,
    )
    selected_CSQ_criteria: str | None = Field(
        validation_alias=AliasChoices(
            "selected_CSQ_criteria",
            "selectedCSQ_criteria",
            "selectedCSQCriteria",
        ),
        default=None,
    )

    @field_validator("variant_callers", mode="before")
    @classmethod
    def _normalize_variant_callers(cls, value: Any) -> Any:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item for item in value.split("|") if item]
        return value


class VariantGtDoc(_DocBase):
    AF: float | int | str | None = None
    DP: int | None = None
    GT: str | None = None
    VD: int | None = None
    sample: str | None = None
    type: str | None = None


class SamplesDoc(_DocBase):
    name: str
    assay: str
    subpanel: str | None = None
    profile: Literal["production", "development", "test", "validation"] | None = None
    genome_build: int | None = None
    case_id: str
    control_id: str | None = None
    sample_no: int
    sequencing_scope: Literal["panel", "wgs", "wts", "targeted"] | None = None
    omics_layer: Literal["DNA", "RNA"] | None = None
    sequencing_technology: str | None = None
    pipeline: str | None = None
    pipeline_version: str | None = None
    vcf_files: str | None = None
    cnv: str | None = None
    cnvprofile: str | None = None
    transloc: str | None = None
    biomarkers: str | None = None
    fusion_files: str | None = None
    expression_path: str | None = None
    classification_path: str | None = None
    qc: str | None = None
    filters: SampleFiltersDoc | None = None
    comments: list[SampleCommentDoc] | None = None
    reports: list[SampleReportDoc] | None = None
    case: SampleCaseControlDoc | None = None
    control: SampleCaseControlDoc | None = None
    groups: list[str] | None = None
    time_added: Any | None = None
    clarity_sample_id: str | None = Field(
        validation_alias=AliasChoices("clarity_sample_id", "clarity-sample-id"),
        default=None,
    )
    clarity_pool_id: str | None = Field(
        validation_alias=AliasChoices("clarity_pool_id", "clarity-pool-id"),
        default=None,
    )

    @field_validator("profile", mode="before")
    @classmethod
    def _normalize_profile(cls, value: Any) -> Any:
        if value is None:
            return None
        raw = str(value).strip().lower()
        aliases = {
            "prod": "production",
            "production": "production",
            "dev": "development",
            "development": "development",
            "test": "test",
            "testing": "test",
            "validation": "validation",
            "stage": "validation",
            "staging": "validation",
        }
        if raw not in aliases:
            raise ValueError("profile must be one of: production, development, test, validation")
        return aliases[raw]


class VariantsDoc(_DocBase):
    SAMPLE_ID: str
    CHROM: str
    POS: int
    REF: str
    ALT: str
    FILTER: list[str] | str | None = None
    ID: str | None = None
    QUAL: float | int | None = None
    INFO: VariantInfoDoc = Field(default_factory=VariantInfoDoc)
    GT: list[VariantGtDoc] = Field(default_factory=list)
    selected_csq_feature: str | None = None
    genes: list[str] | None = None
    transcripts: list[str] | None = None
    HGVSc: list[str] | None = None
    HGVSp: list[str] | None = None
    simple_id: str | None = None
    simple_id_hash: str | None = None
    variant_class: str | None = None
    cosmic_ids: list[str] | None = None
    dbsnp_id: str | None = None
    pubmed_ids: list[str] | None = None
    gnomad_frequency: float | str | None = None
    gnomad_max: float | str | None = None
    exac_frequency: float | str | None = None
    thousandG_frequency: float | str | None = None
    hotspots: list[dict[str, list[str]]] | None = None


class CnvsDoc(_DocBase):
    SAMPLE_ID: str
    chr: str
    start: int
    end: int
    size: int | None = None
    ratio: float | int | None = None
    nprobes: int | None = None
    genes: list[str] | str | None = None
    callers: list[str] | str | None = None


class TranslocationsDoc(_DocBase):
    SAMPLE_ID: str
    CHROM: str
    POS: int
    REF: str
    ALT: str
    FILTER: list[str] | str | None = None
    FORMAT: list[str] | str | None = None
    GT: list[dict[str, Any]] | None = None
    ID: str | None = None
    QUAL: float | int | None = None
    INFO: dict[str, Any] = Field(default_factory=dict)


class BiomarkersDoc(_DocBase):
    SAMPLE_ID: str
    name: str | None = None
    HRD: Any | None = None
    MSIS: Any | None = None
    MSIP: Any | None = None


class CoverageDoc(_DocBase):
    SAMPLE_ID: str
    sample: str | None = None
    chr: str | None = None
    start: int | None = None
    end: int | None = None
    avg_cov: float | int | None = None
    amplicon: str | None = None


class GeneCoverageAmpliconDoc(_DocBase):
    chr: str | None = None
    start: str | int | None = None
    end: str | int | None = None
    nbr: str | int | None = None


class PanelCovDoc(_DocBase):
    SAMPLE_ID: str
    sample: str | None = None
    genes: dict[str, dict[str, dict[str, GeneCoverageAmpliconDoc]]] | dict[str, Any] | None = None


class FusionsDoc(_DocBase):
    SAMPLE_ID: str


class RnaExpressionDoc(_DocBase):
    SAMPLE_ID: str


class RnaClassificationDoc(_DocBase):
    SAMPLE_ID: str


class RnaQcDoc(_DocBase):
    SAMPLE_ID: str


class UsersDoc(_DocBase):
    email: str
    firstname: str | None = None
    lastname: str | None = None
    fullname: str | None = None
    job_title: str | None = None
    auth_type: str | None = None
    password: str | None = None
    role: str | None = None
    environments: list[str] | None = None
    assays: list[str] | None = None
    assay_groups: list[str] | None = None
    is_active: bool | None = None
    permissions: list[str] | None = None
    deny_permissions: list[str] | None = None


class RolesDoc(_DocBase):
    role_id: str
    name: str | None = None
    label: str | None = None
    description: str | None = None
    color: str | None = None
    level: int | float | None = None
    is_active: bool | None = None
    permissions: list[str] | None = None
    deny_permissions: list[str] | None = None
    version_history: list[VersionHistoryEntryDoc] | None = None


class PermissionsDoc(_DocBase):
    permission_id: str
    permission_name: str
    label: str | None = None
    category: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None
    version_history: list[VersionHistoryEntryDoc] | None = None


class AnnotationDoc(_DocBase):
    variant: str
    gene: str
    author: str | None = None
    nomenclature: str | None = None
    transcript: str | None = None
    time_created: Any | None = None
    class_: int | None = Field(default=None, alias="class")
    text: str | None = None


class ReportedVariantsDoc(_DocBase):
    report_id: str
    sample_name: str
    report_oid: Any | None = None
    sample_oid: Any | None = None
    var_oid: Any | None = None
    annotation_oid: Any | None = None
    annotation_text_oid: Any | None = None
    sample_comment_oid: Any | None = None
    simple_id: str | None = None
    simple_id_hash: str | None = None
    gene: str | None = None
    transcript: str | None = None
    hgvsc: str | None = None
    hgvsp: str | None = None
    variant: str | None = None
    var_type: str | None = None
    tier: int | None = None
    created_by: str | None = None
    created_on: Any | None = None


class AspConfigDoc(_DocBase):
    aspc_id: str
    assay_name: str | None = None
    environment: str | None = None
    asp_group: str | None = None
    vep_consequences: list[str] | None = None
    cnveffects: list[str] | None = None
    analysis_types: list[str] | None = None
    report_sections: list[str] | None = None
    version_history: list[VersionHistoryEntryDoc] | None = None


class AssaySpecificPanelsDoc(_DocBase):
    asp_id: str
    assay_name: str | None = None
    asp_group: str | None = None
    asp_family: str | None = None
    asp_category: str | None = None
    display_name: str | None = None
    description: str | None = None
    covered_genes: list[str] | None = None
    germline_genes: list[str] | None = None
    is_active: bool | None = None
    version_history: list[VersionHistoryEntryDoc] | None = None


class InsilicoGenelistsDoc(_DocBase):
    isgl_id: str
    diagnosis: list[str] | str | None = None
    name: str | None = None
    displayname: str | None = None
    list_type: str | None = None
    adhoc: bool | None = None
    is_public: bool | None = None
    is_active: bool | None = None
    assay_groups: list[str] | None = None
    genes: list[str] | None = None
    assays: list[str] | None = None
    version_history: list[VersionHistoryEntryDoc] | None = None


class BlacklistDoc(_DocBase):
    pos: str
    assay: str | None = None
    in_normal_perc: float | int | str | None = None


class BrcaExchangeDoc(_DocBase):
    id: str
    chr: str | None = None
    pos: int | str | None = None
    ref: str | None = None
    alt: str | None = None
    chr38: str | None = None
    pos38: int | str | None = None
    ref38: str | None = None
    alt38: str | None = None


class CivicGenesDoc(_DocBase):
    gene_id: int | str
    name: str
    description: str | None = None
    entrez_id: int | str | None = None


class CivicVariantsDoc(_DocBase):
    variant: str
    gene: str | None = None
    entrez_id: int | str | None = None
    chromosome: str | None = None
    start: int | str | None = None
    stop: int | str | None = None
    reference_bases: str | None = None
    variant_bases: str | None = None


class CosmicDoc(_DocBase):
    id: str
    chr: str
    start: int | str
    end: int | str
    cnt: int | str | None = None


class DashboardMetricsDoc(_DocBase):
    payload: dict[str, Any]
    updated_at: Any | None = None


class GroupCoverageDoc(_DocBase):
    SAMPLE_ID: str
    sample: str | None = None
    genes: dict[str, dict[str, dict[str, GeneCoverageAmpliconDoc]]] | dict[str, Any] | None = None


class HgncGenesDoc(_DocBase):
    hgnc_id: str
    hgnc_symbol: str
    gene_name: str | None = None
    ensembl_gene_id: str | None = None
    entrez_id: str | int | None = None
    refseq_accession: list[str] | str | None = None
    ensembl_mane_select: str | None = None
    refseq_mane_select: str | None = None
    locus: str | None = None
    alias_symbol: list[str] | str | None = None
    alias_name: list[str] | str | None = None
    prev_symbol: list[str] | str | None = None
    prev_name: list[str] | str | None = None
    omim_id: list[int] | list[str] | None = None
    cosmic: list[str] | None = None
    gene_type: list[str] | str | None = None
    refseq_mane_plus_clinical: list[str] | None = None
    addtional_transcript_info: dict[str, dict[str, Any]] | None = None


class HpaExprDoc(_DocBase):
    tid: str
    expr: Any


class IarcTp53Doc(_DocBase):
    id: str
    var: str | None = None
    transactivation_class: str | None = None
    structure_function_class: str | None = None


class ManeSelectDoc(_DocBase):
    gene: str
    ensg: str | None = None
    enst: str | None = None
    refseq: str | None = None


class OncoKbActionableDoc(_DocBase):
    alteration: str = Field(validation_alias=AliasChoices("Alteration", "alteration"))


class OncoKbGenesDoc(_DocBase):
    name: str
    description: str | None = None


class RefSeqCanonicalDoc(_DocBase):
    gene: str
    canonical: str


class VepMetadataDoc(_DocBase):
    source: str
    created_by: str | None = None
    created_on: Any | None = None
    db_info: dict[str, dict[str, Any]] | None = None
    conseq_translations: dict[str, str] | None = None
    variant_class_translations: dict[str, str] | None = None


COLLECTION_MODEL_ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "samples": TypeAdapter(SamplesDoc),
    "variants": TypeAdapter(VariantsDoc),
    "cnvs": TypeAdapter(CnvsDoc),
    "translocations": TypeAdapter(TranslocationsDoc),
    "biomarkers": TypeAdapter(BiomarkersDoc),
    "coverage": TypeAdapter(CoverageDoc),
    "panel_cov": TypeAdapter(PanelCovDoc),
    "fusions": TypeAdapter(FusionsDoc),
    "rna_expression": TypeAdapter(RnaExpressionDoc),
    "rna_classification": TypeAdapter(RnaClassificationDoc),
    "rna_qc": TypeAdapter(RnaQcDoc),
    "users": TypeAdapter(UsersDoc),
    "roles": TypeAdapter(RolesDoc),
    "permissions": TypeAdapter(PermissionsDoc),
    "annotation": TypeAdapter(AnnotationDoc),
    "reported_variants": TypeAdapter(ReportedVariantsDoc),
    "asp_configs": TypeAdapter(AspConfigDoc),
    "assay_specific_panels": TypeAdapter(AssaySpecificPanelsDoc),
    "insilico_genelists": TypeAdapter(InsilicoGenelistsDoc),
    "blacklist": TypeAdapter(BlacklistDoc),
    "brcaexchange": TypeAdapter(BrcaExchangeDoc),
    "civic_genes": TypeAdapter(CivicGenesDoc),
    "civic_variants": TypeAdapter(CivicVariantsDoc),
    "cosmic": TypeAdapter(CosmicDoc),
    "dashboard_metrics": TypeAdapter(DashboardMetricsDoc),
    "group_coverage": TypeAdapter(GroupCoverageDoc),
    "hgnc_genes": TypeAdapter(HgncGenesDoc),
    "hpaexpr": TypeAdapter(HpaExprDoc),
    "iarc_tp53": TypeAdapter(IarcTp53Doc),
    "mane_select": TypeAdapter(ManeSelectDoc),
    "oncokb_actionable": TypeAdapter(OncoKbActionableDoc),
    "oncokb_genes": TypeAdapter(OncoKbGenesDoc),
    "refseq_canonical": TypeAdapter(RefSeqCanonicalDoc),
    "vep_metadata": TypeAdapter(VepMetadataDoc),
}


def validate_collection_document(collection: str, payload: dict[str, Any]) -> None:
    """Validate one document against the mapped collection model."""
    adapter = COLLECTION_MODEL_ADAPTERS.get(collection)
    if not adapter:
        raise ValueError(f"No DB document model registered for collection '{collection}'")
    adapter.validate_python(payload)
