"""Annotation identity and versioned VEP collection contracts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Literal

from pydantic import Field, field_validator, model_validator

from coyote3.contracts.schemas.base import _DocBase, _StrictCollectionDocBase, _StrictDocBase
from coyote3.contracts.schemas.normalizers import normalize_ampersand_terms
from coyote3.domain.annotation_identity import (
    NOMENCLATURE_FIELDS,
    NOMENCLATURE_REQUIRED_FIELDS,
    primary_small_variant_identity,
)


class AnnotationDoc(_StrictCollectionDocBase):
    """Classification or text annotation with nomenclature-specific finding identity."""

    variant: str
    hgvsp: str | None = None
    hgvsc: str | None = None
    genomic: str | None = None
    genomic_hash: str | None = None
    gene: str | None = None
    gene1: str | None = None
    gene2: str | None = None
    asp_group: str
    diagnosis_id: str
    asp_id: str | None
    namespace: Literal["clinical", "sandboxed"]
    author: str
    nomenclature: Literal["p", "g", "c", "f", "cn", "t"]
    transcript: str | None = None
    time_created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class_: int | None = Field(default=None, alias="class")
    text: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_unrelated_identity_fields(cls, value: Any) -> Any:
        """Reject identity fields that do not belong to the selected nomenclature.

        Args:
            value: Raw annotation input; non-dictionaries pass through.

        Returns:
            The input unchanged for allowed fields or an unrecognized nomenclature.

        Raises:
            ValueError: If a known nomenclature includes an unrelated identity key,
                including one whose value is null.
        """
        if not isinstance(value, dict):
            return value
        nomenclature = str(value.get("nomenclature") or "").strip().lower()
        allowed = NOMENCLATURE_FIELDS.get(nomenclature)
        if allowed is None:
            return value
        identity_fields = set().union(*NOMENCLATURE_FIELDS.values())
        identity_fields.update({"cnv", "fusion", "translocation"})
        unrelated = sorted(field for field in value if field in identity_fields - allowed)
        if unrelated:
            raise ValueError(
                f"nomenclature '{nomenclature}' does not allow: {', '.join(unrelated)}"
            )
        return value

    @model_validator(mode="after")
    def validate_annotation_shape(self):
        """Check annotation content exclusivity and nomenclature-specific key presence.

        Returns:
            Validated annotation with the preferred primary identity and nomenclature.

        Raises:
            ValueError: If both or neither of class and text are nonnull, required
                identity keys were not supplied, or unrelated identity keys were supplied.

        Notes:
            Required identity keys may hold null where their field types allow it;
            presence is checked separately from value completeness.
        """
        if self.nomenclature in {"p", "c", "g"}:
            self.nomenclature, self.variant = primary_small_variant_identity(self.model_dump())
        if (self.class_ is None and self.text is None) or (
            self.class_ is not None and self.text is not None
        ):
            raise ValueError("Exactly one of 'class' or 'text' must be provided")

        values = {
            "variant": self.variant,
            "hgvsp": self.hgvsp,
            "hgvsc": self.hgvsc,
            "genomic": self.genomic,
            "genomic_hash": self.genomic_hash,
            "gene": self.gene,
            "gene1": self.gene1,
            "gene2": self.gene2,
            "transcript": self.transcript,
        }
        required = NOMENCLATURE_REQUIRED_FIELDS[self.nomenclature]
        allowed = NOMENCLATURE_FIELDS[self.nomenclature]
        missing = sorted(field for field in required if field not in self.model_fields_set)
        if missing:
            raise ValueError(
                f"nomenclature '{self.nomenclature}' requires keys: {', '.join(missing)}"
            )
        unrelated = sorted(
            field for field in values if field not in allowed and field in self.model_fields_set
        )
        if unrelated:
            raise ValueError(
                f"nomenclature '{self.nomenclature}' does not allow: {', '.join(unrelated)}"
            )
        return self


class VepAnnoTranscriptDoc(_DocBase):
    """Parsed VEP transcript consequence used by the versioned annotation vault."""

    Feature: str | None = None
    HGNC_ID: str | None = None
    SYMBOL: str | None = None
    HGVSc: str | None = None
    HGVSp: str | None = None
    Consequence: list[str] = Field(default_factory=list)
    IMPACT: str | None = None
    EXON: str | None = None
    INTRON: str | None = None
    BIOTYPE: str | None = None
    ENSP: str | None = None
    CANONICAL: str | None = None
    MANE_SELECT: str | None = None
    MANE_PLUS_CLINICAL: str | None = None
    SIFT: str | None = None
    PolyPhen: str | None = None
    CADD_PHRED: str | float | int | None = None
    CLIN_SIG: list[str] = Field(default_factory=list)
    VARIANT_CLASS: str | None = None

    @field_validator("Consequence", "CLIN_SIG", mode="before")
    @classmethod
    def normalize_term_lists(cls, value: Any) -> list[str]:
        """Split ampersand-delimited annotation terms and remove blanks and duplicates.

        Args:
            value: Scalar or iterable of terms; null and empty input give no terms.

        Returns:
            Stripped terms in first-occurrence order.
        """
        return normalize_ampersand_terms(value)


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


class VepDbInfoDoc(_DocBase):
    """Assembly and database versions used by a VEP annotation installation."""

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
    published_sources: dict[str, str] | None = Field(
        default=None,
        description="Original source labels and values from this release's Ensembl cache table.",
    )

    @field_validator("ensembl_version", mode="before")
    @classmethod
    def convert_ensembl(cls, v):
        """Convert the Ensembl version using Python integer conversion.

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


class VepVariantClassDoc(_DocBase):
    """Display translation and Sequence Ontology term for a VEP variant class."""

    short: str
    desc: str
    displayname: str
    so_term: str


class VepConsequenceDoc(_DocBase):
    """Consequence display translation with impact, ontology term, and group."""

    short: str
    display: str
    desc: str
    impact: str
    so_term: str
    group: str


class VepDiagramAssetDoc(_StrictCollectionDocBase):
    """Content-addressed image stored as BSON binary in the knowledgebase."""

    id_: str = Field(alias="_id", pattern=r"^[a-f0-9]{64}$")
    data: bytes = Field(
        max_length=2_000_000, description="Original image bytes, BSON binary subtype 0."
    )
    mime_type: Literal["image/jpeg", "image/png", "image/svg+xml"]

    @model_validator(mode="after")
    def verify_digest(self):
        """Reject image data whose SHA-256 differs from its content-addressed ID.

        Returns:
            The validated binary asset.

        Raises:
            ValueError: Image content differs from its declared digest.
        """
        if hashlib.sha256(self.data).hexdigest() != self.id_:
            raise ValueError("VEP diagram checksum mismatch")
        return self


class VepConsequenceDiagramDoc(_StrictDocBase):
    """Compact Ensembl diagram descriptor; sha256 identifies a separate binary asset."""

    mime_type: Literal["image/jpeg", "image/png", "image/svg+xml"]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_url: str
    release: str


class VepMetadataDoc(_DocBase):
    """Versioned VEP database metadata, display translations, and consequence groups."""

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
    consequence_diagram: VepConsequenceDiagramDoc | None = None

    @field_validator("vep_id", mode="before")
    @classmethod
    def derive_vep_id(cls, value, info):
        """Keep an explicit VEP ID or derive one from available parsed database metadata.

        Args:
            value: Supplied ID; null or blank text requests derivation.
            info: Pydantic validation context whose data may contain db_info dictionaries.

        Returns:
            The stripped supplied ID or the sole Ensembl version found in that context.

        Raises:
            ValueError: If derivation does not find exactly one distinct version.

        Notes:
            Only fields already available in info.data are inspected; this validator
            does not read later fields from the raw model input.
        """
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
        """Require each grouped consequence term to have a translation entry.

        Returns:
            This VEP metadata document unchanged.

        Raises:
            ValueError: If any consequence group names a term absent from conseq_translations.
        """
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
