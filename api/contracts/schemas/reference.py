"""Reference, annotation, and auxiliary collection contracts."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Literal

from pydantic import Field, field_validator, model_validator

from api.contracts.schemas.base import _DocBase


class AnnotationDoc(_DocBase):
    variant: str
    gene: str
    assay: str
    subpanel: str
    author: str
    nomenclature: Literal["p", "g", "c", "f"]
    transcript: str
    time_created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class_: int | None = Field(default=None, alias="class")
    text: str | None = None

    @model_validator(mode="after")
    def validate_class_xor_text(self):
        if (self.class_ is None and self.text is None) or (
            self.class_ is not None and self.text is not None
        ):
            raise ValueError("Exactly one of 'class' or 'text' must be provided")
        return self


class VepAnnoTranscriptDoc(_DocBase):
    """Parsed VEP transcript consequence used by the versioned annotation vault."""

    Feature: str | None = None
    HGNC_ID: str | None = None
    SYMBOL: str | None = None
    VEP_SYMBOL: str | None = None
    HGNC_MATCHED: bool | None = None
    HGNC_MATCH_SOURCE: str | None = None
    HGVSc: str | None = None
    HGVSp: str | None = None
    Consequence: list[str] = Field(default_factory=list)
    IMPACT: str | None = None
    EXON: str | None = None
    INTRON: str | None = None
    BIOTYPE: str | None = None
    ENSP: str | None = None
    CANONICAL: str | None = None
    MANE: str | None = None
    MANE_PLUS_CLINICAL: str | None = None
    SIFT: str | None = None
    PolyPhen: str | None = None
    CADD_PHRED: str | float | int | None = None
    CLIN_SIG: str | None = None
    VARIANT_CLASS: str | None = None
    transcript_tags: list[str] = Field(default_factory=list)
    canonical_source: str | None = None
    is_canonical: bool = False

    @field_validator("Consequence", mode="before")
    @classmethod
    def normalize_consequence(cls, value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [term for term in value.split("&") if term]
        return value

    @field_validator("transcript_tags", mode="before")
    @classmethod
    def normalize_transcript_tags(cls, value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [value]
        return list(value)


class AnnoVepDoc(_DocBase):
    """Immutable transcript consequence vault keyed by variant identity and VEP version."""

    simple_id: str
    simple_id_hash: str
    vep_version: str
    variant_class: str | None = None
    CSQ: list[VepAnnoTranscriptDoc] = Field(default_factory=list)

    @field_validator("vep_version", mode="before")
    @classmethod
    def normalize_vep_version(cls, value: Any) -> str:
        """Store VEP versions as plain version numbers."""
        return str(value or "").strip().lstrip("vV")


class BrcaExchangeDoc(_DocBase):
    id: str

    chr: str
    pos: int
    ref: str
    alt: str

    chr38: str
    pos38: int
    ref38: str
    alt38: str

    enigma_clinsig: str
    enigma_clinsig_refs: str
    enigma_clinsig_comment: str

    @field_validator("pos", "pos38", mode="before")
    @classmethod
    def convert_pos_to_int(cls, v):
        return int(v)

    @field_validator("chr", "chr38")
    @classmethod
    def validate_chr(cls, v):
        # allow numeric chromosomes + X/Y
        if v not in {str(i) for i in range(1, 23)} | {"X", "Y", "MT", "M"}:
            raise ValueError(f"Invalid chromosome: {v}")
        if v == "M":
            v = "MT"
        return v


class CivicGenesDoc(_DocBase):
    gene_id: int
    entrez_id: int
    name: str

    description: str
    gene_civic_url: str

    last_review_date: datetime

    @field_validator("gene_id", "entrez_id", mode="before")
    @classmethod
    def convert_ids(cls, v):
        return int(v)

    @field_validator("last_review_date", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        # Example: "2017-03-06 00:00:15 UTC"
        return datetime.strptime(v, "%Y-%m-%d %H:%M:%S %Z")

    @field_validator("gene_civic_url")
    @classmethod
    def validate_url(cls, v):
        if not v.startswith("http"):
            raise ValueError("Invalid URL")
        return v


class CivicVariantsDoc(_DocBase):
    variant_id: int
    entrez_id: int

    gene: str
    variant: str
    summary: str

    variant_types: str
    variant_groups: str

    chromosome: str
    start: int
    stop: int

    chromosome2: str
    start2: int
    stop2: int

    reference_build: str
    ensembl_version: int

    representative_transcript: str
    representative_transcript2: str

    reference_bases: str
    variant_bases: str

    hgvs_expressions: list[str]

    civic_actionability_score: float
    variant_civic_url: str
    last_review_date: datetime

    @field_validator(
        "variant_id",
        "entrez_id",
        "start",
        "stop",
        "start2",
        "stop2",
        "ensembl_version",
        mode="before",
    )
    @classmethod
    def convert_int_fields(cls, v):
        return int(v)

    @field_validator("civic_actionability_score", mode="before")
    @classmethod
    def convert_score(cls, v):
        return float(v)

    @field_validator("last_review_date", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        return datetime.strptime(v, "%Y-%m-%d %H:%M:%S %Z")

    @field_validator("variant_civic_url")
    @classmethod
    def validate_url(cls, v):
        if not v.startswith("http"):
            raise ValueError("Invalid URL")
        return v

    @field_validator("chromosome", "chromosome2")
    @classmethod
    def validate_chr(cls, v):
        allowed = {str(i) for i in range(1, 23)} | {"X", "Y", "MT", "M"}
        if v not in allowed:
            raise ValueError(f"Invalid chromosome: {v}")
        if v == "M":
            v = "MT"
        return v


class CosmicDoc(_DocBase):
    id: str

    chr: int
    start: int
    end: int

    cnt: Dict[str, int]

    @field_validator("chr")
    @classmethod
    def validate_chr(cls, v):
        allowed = {str(i) for i in range(1, 23)} | {"X", "Y", "MT", "M"}
        if v not in allowed:
            raise ValueError(f"Invalid chromosome: {v}")
        if v == "M":
            v = "MT"
        return v

    @field_validator("start", "end")
    @classmethod
    def validate_positions(cls, v):
        if v < 0:
            raise ValueError("Position must be positive")
        return v

    @field_validator("cnt")
    @classmethod
    def validate_counts(cls, v):
        for k, val in v.items():
            if not isinstance(k, str):
                raise ValueError("cnt keys must be strings")
            if not isinstance(val, int) or val < 0:
                raise ValueError(f"Invalid count for {k}")
        return v


class HgncAdditionalTranscriptInfoDoc(_DocBase):
    start: int
    end: int
    length: int
    start_site: int


class HgncGenesDoc(_DocBase):
    hgnc_id: str
    hgnc_symbol: str
    gene_name: str
    status: str

    locus: str
    locus_sortable: str

    alias_symbol: list[str] = Field(default_factory=list)
    alias_name: list[str] = Field(default_factory=list)
    prev_symbol: list[str] = Field(default_factory=list)
    prev_name: list[str] = Field(default_factory=list)

    date_approved_reserved: datetime | None = None
    date_symbol_changed: datetime | None = None
    date_name_changed: datetime | None = None
    date_modified: datetime | None = None

    entrez_id: int
    ensembl_gene_id: str
    refseq_accession: list[str] = Field(default_factory=list)

    cosmic: list[str] = Field(default_factory=list)
    omim_id: list[int] = Field(default_factory=list)
    pseudogene_org: list[str] = Field(default_factory=list)

    imgt: str | None = None
    lncrnadb: str | None = None
    lncipedia: str | None = None

    ensembl_mane_select: str
    refseq_mane_select: str

    chromosome: str
    other_chromosome: str | None = None

    start: int
    end: int
    gene_gc_content: float
    gene_description: str

    ensembl_canonical: bool
    gene_type: list[str] = Field(default_factory=list)
    refseq_mane_plus_clinical: list[str] = Field(default_factory=list)

    addtional_transcript_info: dict[str, HgncAdditionalTranscriptInfoDoc] = Field(
        default_factory=dict
    )


class HpaExprDoc(_DocBase):
    tid: str
    expr: dict[str, float] = Field(default_factory=dict)

    @field_validator("expr")
    @classmethod
    def validate_expr(cls, v):
        for tissue, value in v.items():
            if not isinstance(tissue, str):
                raise ValueError("All expr keys must be strings")
            if not isinstance(value, (int, float)):
                raise ValueError(f"Expression value for '{tissue}' must be numeric")
            if value < 0:
                raise ValueError(f"Expression value for '{tissue}' cannot be negative")
        return v


class IarcTp53Doc(_DocBase):
    id: int
    var: str

    polymorphism: str
    cpg: str
    splice: str

    transactivation_class: str
    AGVGD_class: str
    residue_func: str
    motif: str
    structure_function_class: str
    domain_func: str

    n_somatic: int
    n_germline: int

    topology_count: int | None = None

    @field_validator("id", "n_somatic", "n_germline", mode="before")
    @classmethod
    def convert_int_fields(cls, v):
        return int(v)

    @field_validator("topology_count", mode="before")
    @classmethod
    def convert_optional_int(cls, v):
        if v is None or v == "":
            return None
        return int(v)


class ManeSelectDoc(_DocBase):
    gene: str
    enst: str
    refseq: str
    ensg: str

    @field_validator("ensg")
    def validate_ensg(cls, v):
        if not re.match(r"^ENSG\d+$", v):
            raise ValueError("Invalid ENSG format")
        return v

    @field_validator("enst")
    def validate_enst(cls, v):
        if not re.match(r"^ENST\d+$", v):
            raise ValueError("Invalid ENST format")
        return v


class OncoKbActionableDoc(_DocBase):
    RefSeq: str
    Alteration: str
    Isoform: str

    Drugs_s: str = Field(alias="Drugs(s)")
    Level: str
    Cancer_Type: str = Field(alias="Cancer Type")

    Entrez_Gene_ID: int = Field(alias="Entrez Gene ID")
    Hugo_Symbol: str = Field(alias="Hugo Symbol")

    Protein_Change: str = Field(alias="Protein Change")
    PMIDs_for_drug: str = Field(alias="PMIDs for drug")

    @field_validator("Entrez_Gene_ID", mode="before")
    @classmethod
    def convert_entrez(cls, v):
        return int(v)


class OncoKbGenesDoc(_DocBase):
    name: str
    description: str


class OncoKbPublicDoc(_DocBase):
    query_hash: str
    gene: str
    alteration: str | None = None
    reference_genome: str | None = None
    public_api: bool = True
    therapeutic_data_included: bool = False
    source: str | None = None
    license: str | None = None
    query: dict | None = None
    response: dict | None = None
    data_version: str | None = None
    gene_exist: bool | None = None
    variant_exist: bool | None = None
    variant_ids: list[str] = Field(default_factory=list)
    sample_ids: list[str] = Field(default_factory=list)
    sample_names: list[str] = Field(default_factory=list)


class OncoKbGenesPublicDoc(_DocBase):
    gene: str
    source: str | None = None
    public_api: bool = True
    therapeutic_data_included: bool = False
    data_version: str | None = None
    gene_exist: bool | None = None
    gene_summary: str | None = None
    background: str | None = None
    setting: str | None = None
    entrez_gene_id: int | None = None
    gene_type: str | None = None
    highest_sensitive_level: str | None = None
    highest_resistance_level: str | None = None
    grch37_refseq: str | None = None
    grch37_isoform: str | None = None
    grch38_refseq: str | None = None
    grch38_isoform: str | None = None
    hgnc_id: str | None = None
    previous_symbols: list[str] = Field(default_factory=list)
    alias_symbols: list[str] = Field(default_factory=list)


class OncoKbCancerGenesPublicDoc(_DocBase):
    """Public OncoKB cancer-gene list record from /utils/cancerGeneList."""

    gene: str
    source: str | None = None
    public_api: bool = True
    therapeutic_data_included: bool = False
    data_version: str | None = None
    hgnc_id: str | None = None
    previous_symbols: list[str] = Field(default_factory=list)
    alias_symbols: list[str] = Field(default_factory=list)
    entrez_gene_id: int | None = None
    gene_type: str | None = None
    occurrence_count: int | None = None
    oncokb_annotated: bool | None = None
    sanger_cgc: bool | None = None
    vogelstein: bool | None = None
    foundation: bool | None = None
    foundation_heme: bool | None = None
    msk_impact: bool | None = None
    msk_heme: bool | None = None
    grch37_refseq: str | None = None
    grch37_isoform: str | None = None
    grch38_refseq: str | None = None
    grch38_isoform: str | None = None


class ClinPgxGenesPublicDoc(_DocBase):
    """Public ClinPGx gene cache record imported from genes.tsv."""

    pharmgkb_accession_id: str
    ncbi_gene_id: int | None = None
    hgnc_id: str | None = None
    ensembl_id: str | None = None
    name: str | None = None
    symbol: str
    alternate_names: list[str] = Field(default_factory=list)
    alternate_symbols: list[str] = Field(default_factory=list)
    is_vip: bool = False
    has_variant_annotation: bool = False
    has_cpic_dosing_guideline: bool = False
    cross_references: list[str] = Field(default_factory=list)
    chromosome: str | None = None
    grch37_start: int | None = None
    grch37_stop: int | None = None
    grch38_start: int | None = None
    grch38_stop: int | None = None
    source: str | None = None
    source_file: str | None = None
    source_reference: str | None = None
    source_created: str | None = None
    public_api: bool = True
    last_seen_at: datetime | None = None


class RefSeqCanonicalDoc(_DocBase):
    gene: str
    canonical: str


class VepDbInfoDoc(_DocBase):
    assembly_name: str
    assembly_accession: str
    genome_assembly: str
    genome_build: str

    ensembl_version: int
    gencode: str
    refseq: str

    regulatory_build: str
    polyphen: str
    sift: str

    dbsnp: str
    cosmic: str
    hgmd_public: str
    clinvar: str

    genomes_1000: str = Field(alias="1000_genomes")
    nhlbi_esp: str
    gnomad: str

    @field_validator("ensembl_version", mode="before")
    @classmethod
    def convert_ensembl(cls, v):
        return int(v)


class VepVariantClassDoc(_DocBase):
    short: str
    desc: str
    displayname: str
    so_term: str


class VepConsequenceDoc(_DocBase):
    short: str
    display: str
    desc: str
    impact: str
    so_term: str
    group: str


class VepMetadataDoc(_DocBase):
    vep_id: str
    created_by: str
    created_on: datetime

    source: str
    vc_translation_source: str
    conseq_translation_source: str

    db_info: Dict[str, VepDbInfoDoc]

    variant_class_translations: Dict[str, VepVariantClassDoc]
    conseq_translations: Dict[str, VepConsequenceDoc]
    consequence_groups: Dict[str, list[str]]

    @field_validator("vep_id", mode="before")
    @classmethod
    def derive_vep_id(cls, value, info):
        if value is not None and str(value).strip():
            return str(value).strip()
        raw = info.data or {}
        db_info = raw.get("db_info") or {}
        versions = {
            str(meta.get("ensembl_version")).strip()
            for meta in db_info.values()
            if isinstance(meta, dict) and meta.get("ensembl_version") is not None
        }
        versions = {version for version in versions if version}
        if len(versions) != 1:
            raise ValueError("vep_metadata requires exactly one resolvable ensembl_version")
        return versions.pop()

    @model_validator(mode="after")
    def validate_consequence_groups_against_translations(self):
        known_terms = set(self.conseq_translations.keys())
        invalid_terms: dict[str, list[str]] = {}
        for group_name, terms in self.consequence_groups.items():
            missing = [term for term in terms if term not in known_terms]
            if missing:
                invalid_terms[group_name] = missing
        if invalid_terms:
            raise ValueError(
                "vep_metadata consequence_groups reference unknown consequence terms: "
                f"{invalid_terms}"
            )
        return self


class DashboardPayloadDoc(_DocBase):
    total_variants: int
    total_snps: int
    fps: int


class DashboardMetricsDoc(_DocBase):
    payload: DashboardPayloadDoc
    updated_at: datetime
