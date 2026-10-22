"""Reference, annotation, and auxiliary collection contracts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Literal

from pydantic import Field, field_validator, model_validator

from api.contracts.schemas.base import _DocBase


class BrcaExchangeDoc(_DocBase):
    """BRCA Exchange alleles, ENIGMA interpretation, and retained source metadata."""

    id: str

    chr: str
    pos: int
    ref: str
    alt: str

    chr38: str | None = None
    pos38: int | None = None
    ref38: str | None = None
    alt38: str | None = None

    enigma_clinsig: str
    enigma_clinsig_refs: str
    enigma_clinsig_comment: str

    gene: str | None = None
    transcript: str | None = None
    hgvsc: str | None = None
    hgvsp: str | None = None
    pathogenicity_expert: str | None = None
    pathogenicity_all: str | None = None
    source_url: str | None = None
    source_record: dict[str, str] = Field(default_factory=dict)

    @field_validator("pos", mode="before")
    @classmethod
    def convert_pos_to_int(cls, v):
        """Convert the position using Python integer conversion.

        Args:
            v: Numeric value or integer text supplied by the source.

        Returns:
            The integer conversion of the input.

        Raises:
            ValueError: If the input cannot be represented as an integer.
            TypeError: If the input does not support integer conversion.
            OverflowError: If the input is an infinite float.
        """
        return int(v)

    @field_validator("pos38", mode="before")
    @classmethod
    def convert_optional_pos_to_int(cls, v):
        """Parse an optional GRCh38 position as an integer.

        Args:
            v: Numeric value or integer text; None and the empty string mean missing.

        Returns:
            The integer conversion, or None for missing input.

        Raises:
            ValueError: If nonempty input cannot be represented as an integer.
            TypeError: If the input does not support integer conversion.
            OverflowError: If the input is an infinite float.
        """
        if v is None or v == "":
            return None
        return int(v)

    @field_validator("chr", "chr38")
    @classmethod
    def validate_chr(cls, v):
        """Validate an unprefixed human chromosome and map M to MT.

        Args:
            v: Chromosome text: 1 through 22, X, Y, M, or MT; None or empty is missing.

        Returns:
            The chromosome, with M replaced by MT, or None for missing input.

        Raises:
            ValueError: If the chromosome is outside the accepted case-sensitive set.
        """
        if v is None or v == "":
            return None
        # allow numeric chromosomes + X/Y
        if v not in {str(i) for i in range(1, 23)} | {"X", "Y", "MT", "M"}:
            raise ValueError(f"Invalid chromosome: {v}")
        if v == "M":
            v = "MT"
        return v


class CivicGenesDoc(_DocBase):
    """CIViC gene record with review timestamp, aliases, and source identifiers."""

    gene_id: int
    entrez_id: int | None = None
    name: str

    description: str | None = None
    gene_civic_url: str

    last_review_date: datetime

    feature_type: str = "Gene"
    aliases: list[str] = Field(default_factory=list)
    ncit_id: str | None = None
    source_record: dict[str, str] = Field(default_factory=dict)

    @field_validator("gene_id", mode="before")
    @classmethod
    def convert_id(cls, v):
        """Convert the CIViC gene identifier using Python integer conversion.

        Args:
            v: Numeric value or integer text supplied by the source.

        Returns:
            The integer conversion of the input.

        Raises:
            ValueError: If the input cannot be represented as an integer.
            TypeError: If the input does not support integer conversion.
            OverflowError: If the input is an infinite float.
        """
        return int(v)

    @field_validator("entrez_id", mode="before")
    @classmethod
    def convert_optional_id(cls, v):
        """Parse an optional Entrez identifier as an integer.

        Args:
            v: Numeric value or integer text; None and the empty string mean missing.

        Returns:
            The integer conversion, or None for missing input.

        Raises:
            ValueError: If nonempty input cannot be represented as an integer.
            TypeError: If the input does not support integer conversion.
            OverflowError: If the input is an infinite float.
        """
        if v is None or v == "":
            return None
        return int(v)

    @field_validator("last_review_date", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        """Parse a CIViC review timestamp from ISO or legacy export text.

        Args:
            v: Datetime or timestamp text; ISO Z is translated to the UTC offset.

        Returns:
            Existing datetimes unchanged, otherwise a parsed datetime. No timezone
            is assigned to inputs that parse without one.

        Raises:
            ValueError: If neither ISO format nor the legacy year-month-day, time,
                and timezone-name format can parse the text.
        """
        if isinstance(v, datetime):
            return v
        value = str(v).strip()
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            # Preserve support for legacy CIViC exports.
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %Z")

    @field_validator("gene_civic_url")
    @classmethod
    def validate_url(cls, v):
        """Require the literal lowercase http prefix on a CIViC link.

        Args:
            v: Source URL text.

        Returns:
            The input unchanged.

        Raises:
            ValueError: If the text does not start with http.

        Notes:
            No URL structure, host, or reachability check is performed.
        """
        if not v.startswith("http"):
            raise ValueError("Invalid URL")
        return v


class CivicVariantsDoc(_DocBase):
    """CIViC variant or fusion record with coordinates, HGVS, and review metadata."""

    variant_id: int
    entrez_id: int | None = None

    gene: str | None = None
    variant: str
    summary: str | None = None

    variant_types: list[str] = Field(default_factory=list)
    variant_groups: list[str] = Field(default_factory=list)

    chromosome: str | None = None
    start: int | None = None
    stop: int | None = None

    chromosome2: str | None = None
    start2: int | None = None
    stop2: int | None = None

    reference_build: str | None = None
    ensembl_version: int | None = None

    representative_transcript: str | None = None
    representative_transcript2: str | None = None

    reference_bases: str | None = None
    variant_bases: str | None = None

    hgvs_expressions: list[str]

    civic_actionability_score: float | None = None
    variant_civic_url: str
    last_review_date: datetime

    feature_type: str | None = None
    feature_id: int | None = None
    feature_name: str | None = None
    feature_civic_url: str | None = None
    variant_aliases: list[str] = Field(default_factory=list)
    is_flagged: bool = False
    molecular_profile_id: int | None = None
    allele_registry_id: str | None = None
    clinvar_ids: list[str] = Field(default_factory=list)
    ncit_id: str | None = None
    five_prime_partner: str | None = None
    three_prime_partner: str | None = None
    vicc_compliant_name: str | None = None
    iscn_name: str | None = None
    source_record: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "variant_id",
        mode="before",
    )
    @classmethod
    def convert_variant_id(cls, v):
        """Convert the CIViC variant identifier using Python integer conversion.

        Args:
            v: Numeric value or integer text supplied by the source.

        Returns:
            The integer conversion of the input.

        Raises:
            ValueError: If the input cannot be represented as an integer.
            TypeError: If the input does not support integer conversion.
            OverflowError: If the input is an infinite float.
        """
        return int(v)

    @field_validator(
        "entrez_id",
        "start",
        "stop",
        "start2",
        "stop2",
        "ensembl_version",
        "feature_id",
        "molecular_profile_id",
        mode="before",
    )
    @classmethod
    def convert_optional_int_fields(cls, v):
        """Parse an optional coordinate, identifier, or Ensembl version as an integer.

        Args:
            v: Numeric value or integer text; None and the empty string mean missing.

        Returns:
            The integer conversion, or None for missing input.

        Raises:
            ValueError: If nonempty input cannot be represented as an integer.
            TypeError: If the input does not support integer conversion.
            OverflowError: If the input is an infinite float.
        """
        if v is None or v == "":
            return None
        return int(v)

    @field_validator("civic_actionability_score", mode="before")
    @classmethod
    def convert_score(cls, v):
        """Parse an optional CIViC actionability score.

        Args:
            v: Numeric score or text; None and the empty string mean missing.

        Returns:
            A float score, or None for missing input.

        Raises:
            ValueError: If nonempty text cannot be parsed as a float.
            TypeError: If the input does not support float conversion.
        """
        if v is None or v == "":
            return None
        return float(v)

    @field_validator("variant_types", "variant_groups", "hgvs_expressions", mode="before")
    @classmethod
    def convert_list_fields(cls, v):
        """Split comma-delimited CIViC types, groups, or HGVS expressions.

        Args:
            v: Source text or existing list; None and the empty string mean no entries.

        Returns:
            Stripped nonblank tokens for text, an empty list for missing input,
            or other input unchanged for field validation.
        """
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [part.strip() for part in v.split(",") if part.strip()]
        return v

    @field_validator("last_review_date", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        """Parse a CIViC review timestamp from ISO or legacy export text.

        Args:
            v: Datetime or timestamp text; ISO Z is translated to the UTC offset.

        Returns:
            Existing datetimes unchanged, otherwise a parsed datetime. No timezone
            is assigned to inputs that parse without one.

        Raises:
            ValueError: If neither ISO format nor the legacy year-month-day, time,
                and timezone-name format can parse the text.
        """
        if isinstance(v, datetime):
            return v
        value = str(v).strip()
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            # Preserve support for legacy CIViC exports.
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %Z")

    @field_validator("variant_civic_url")
    @classmethod
    def validate_url(cls, v):
        """Require the literal lowercase http prefix on a CIViC link.

        Args:
            v: Source URL text.

        Returns:
            The input unchanged.

        Raises:
            ValueError: If the text does not start with http.

        Notes:
            No URL structure, host, or reachability check is performed.
        """
        if not v.startswith("http"):
            raise ValueError("Invalid URL")
        return v

    @field_validator("chromosome", "chromosome2")
    @classmethod
    def validate_chr(cls, v):
        """Validate an unprefixed human chromosome and map M to MT.

        Args:
            v: Chromosome text: 1 through 22, X, Y, M, or MT; None or empty is missing.

        Returns:
            The chromosome, with M replaced by MT, or None for missing input.

        Raises:
            ValueError: If the chromosome is outside the accepted case-sensitive set.
        """
        if v is None or v == "":
            return None
        allowed = {str(i) for i in range(1, 23)} | {"X", "Y", "MT", "M"}
        if v not in allowed:
            raise ValueError(f"Invalid chromosome: {v}")
        if v == "M":
            v = "MT"
        return v


class CosmicDoc(_DocBase):
    """COSMIC variant interval with named occurrence counts."""

    id: str

    chr: str
    start: int
    end: int

    cnt: Dict[str, int]

    @field_validator("chr", mode="before")
    @classmethod
    def validate_chr(cls, v):
        """Normalize a COSMIC chromosome label and validate the human chromosome set.

        Args:
            v: Chromosome value, optionally prefixed by chr in any case.

        Returns:
            Stripped uppercase chromosome without the prefix, mapping M to MT.

        Raises:
            ValueError: If the result is not 1 through 22, X, Y, M, or MT.
        """
        v = str(v).strip().upper().removeprefix("CHR")
        allowed = {str(i) for i in range(1, 23)} | {"X", "Y", "MT", "M"}
        if v not in allowed:
            raise ValueError(f"Invalid chromosome: {v}")
        if v == "M":
            v = "MT"
        return v

    @field_validator("start", "end")
    @classmethod
    def validate_positions(cls, v):
        """Reject negative interval coordinates while allowing zero.

        Args:
            v: Parsed start or end coordinate.

        Returns:
            The coordinate unchanged.

        Raises:
            ValueError: If the coordinate is negative.
        """
        if v < 0:
            raise ValueError("Position must be positive")
        return v

    @field_validator("cnt")
    @classmethod
    def validate_counts(cls, v):
        """Check named COSMIC occurrence counts.

        Args:
            v: Mapping from count labels to integer counts.

        Returns:
            The mapping unchanged.

        Raises:
            ValueError: If a key is not a string or a count is not a nonnegative integer.
        """
        for k, val in v.items():
            if not isinstance(k, str):
                raise ValueError("cnt keys must be strings")
            if not isinstance(val, int) or val < 0:
                raise ValueError(f"Invalid count for {k}")
        return v


class CosmicProductDoc(_DocBase):
    """Common contract for a source-faithful non-variant COSMIC product record."""

    record_key: str
    source_row: int


class KnowledgebaseReleaseDoc(_DocBase):
    """Provenance and publication state for one imported knowledgebase snapshot."""

    source: str
    release: str
    status: Literal["staging", "active", "retired", "failed"]
    import_cpus: int = Field(default=1, ge=1)
    started_at: datetime
    files: list[dict[str, Any]] = Field(default_factory=list)
    collections: list[dict[str, Any]] = Field(default_factory=list)
    published_at: datetime | None = None
    retired_at: datetime | None = None
    failed_at: datetime | None = None


class HgncAdditionalTranscriptInfoDoc(_DocBase):
    """Transcript bounds, length, and start-site metadata attached to an HGNC gene."""

    start: int
    end: int
    length: int
    start_site: int


class HgncGenesDoc(_DocBase):
    """HGNC gene nomenclature with genomic, cross-reference, and transcript metadata."""

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
    ensembl_mane_plus_clinical: list[str] = Field(default_factory=list)

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
    """Tissue expression values associated with an HPA transcript identifier."""

    tid: str
    expr: dict[str, float] = Field(default_factory=dict)

    @field_validator("expr")
    @classmethod
    def validate_expr(cls, v):
        """Check tissue labels and reject nonnumeric or negative expression values.

        Args:
            v: Mapping of tissue names to expression measurements.

        Returns:
            The expression mapping unchanged.

        Raises:
            ValueError: If a tissue key is not a string or a value is nonnumeric or negative.
        """
        for tissue, value in v.items():
            if not isinstance(tissue, str):
                raise ValueError("All expr keys must be strings")
            if not isinstance(value, (int, float)):
                raise ValueError(f"Expression value for '{tissue}' must be numeric")
            if value < 0:
                raise ValueError(f"Expression value for '{tissue}' cannot be negative")
        return v


class IarcTp53Doc(_DocBase):
    """TP53 variant evidence with functional annotations and cohort counts."""

    id: int
    var: str

    polymorphism: str | None = None
    cpg: str | None = None
    splice: str | None = None

    transactivation_class: str | None = None
    AGVGD_class: str | None = None
    residue_func: str | None = None
    motif: str | None = None
    structure_function_class: str | None = None
    domain_func: str | None = None

    n_somatic: int | None = None
    n_germline: int | None = None

    topology_count: int | None = None
    hgvsg_hg19: str | None = None
    hgvsg_hg38: str | None = None
    hgvsp: str | None = None
    effect: str | None = None
    hotspot: str | None = None
    external_cohort_count: int | None = None
    source_record: dict[str, str] = Field(default_factory=dict)

    @field_validator("id", mode="before")
    @classmethod
    def convert_id(cls, v):
        """Convert the TP53 record identifier using Python integer conversion.

        Args:
            v: Numeric value or integer text supplied by the source.

        Returns:
            The integer conversion of the input.

        Raises:
            ValueError: If the input cannot be represented as an integer.
            TypeError: If the input does not support integer conversion.
            OverflowError: If the input is an infinite float.
        """
        return int(v)

    @field_validator(
        "n_somatic", "n_germline", "topology_count", "external_cohort_count", mode="before"
    )
    @classmethod
    def convert_optional_int(cls, v):
        """Parse an optional cohort count as an integer.

        Args:
            v: Numeric value or integer text; None and the empty string mean missing.

        Returns:
            The integer conversion, or None for missing input.

        Raises:
            ValueError: If nonempty input cannot be represented as an integer.
            TypeError: If the input does not support integer conversion.
            OverflowError: If the input is an infinite float.
        """
        if v is None or v == "":
            return None
        return int(v)


class ManeSelectDoc(_DocBase):
    """Gene mapping between Ensembl and RefSeq MANE transcript identifiers."""

    gene: str
    enst: str
    refseq: str
    ensg: str

    @field_validator("ensg")
    def validate_ensg(cls, v):
        """Check the Ensembl gene identifier pattern.

        Args:
            v: Identifier beginning with ENSG followed by digits, without a version suffix.

        Returns:
            The identifier unchanged.

        Raises:
            ValueError: If the ENSG-plus-digits pattern does not match.
        """
        if not re.match(r"^ENSG\d+$", v):
            raise ValueError("Invalid ENSG format")
        return v

    @field_validator("enst")
    def validate_enst(cls, v):
        """Check the Ensembl transcript identifier pattern.

        Args:
            v: Identifier beginning with ENST followed by digits, without a version suffix.

        Returns:
            The identifier unchanged.

        Raises:
            ValueError: If the ENST-plus-digits pattern does not match.
        """
        if not re.match(r"^ENST\d+$", v):
            raise ValueError("Invalid ENST format")
        return v


class OncoKbActionableDoc(_DocBase):
    """OncoKB alteration evidence with drug, cancer-type, and evidence-level fields."""

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
        """Convert the Entrez gene identifier using Python integer conversion.

        Args:
            v: Numeric value or integer text supplied by the source.

        Returns:
            The integer conversion of the input.

        Raises:
            ValueError: If the input cannot be represented as an integer.
            TypeError: If the input does not support integer conversion.
            OverflowError: If the input is an infinite float.
        """
        return int(v)


class OncoKbGenesDoc(_DocBase):
    """OncoKB gene name and descriptive text."""

    name: str
    description: str


class OncoKbPublicDoc(_DocBase):
    """Sample-independent public OncoKB query cache with provenance and response data."""

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

    @model_validator(mode="before")
    @classmethod
    def reject_sample_identity(cls, value: Any) -> Any:
        """Keep shared knowledgebase cache documents independent of samples."""
        if isinstance(value, dict):
            forbidden = sorted({"sample_ids", "sample_names"}.intersection(value))
            if forbidden:
                raise ValueError(
                    f"oncokb_public cannot contain sample identity fields: {', '.join(forbidden)}"
                )
        return value


class OncoKbGenesPublicDoc(_DocBase):
    """Public OncoKB gene summary, identifiers, aliases, and assembly-specific isoforms."""

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
