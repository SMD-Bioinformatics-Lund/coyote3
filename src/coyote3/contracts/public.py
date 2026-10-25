"""Public route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from coyote3.contracts.schemas.public_catalog import PublicAssayCatalogDoc, PublicCatalogRevisionDoc
from coyote3.contracts.schemas.variant_annotations import (
    VepConsequenceDiagramDoc,
    VepConsequenceDoc,
    VepDbInfoDoc,
    VepVariantClassDoc,
)


class PublicVepVersionsPayload(BaseModel):
    """Available installed major VEP references, ordered numerically."""

    versions: list[str]


class PublicVepReferencePayload(BaseModel):
    """Public reference definitions without database IDs or operator identities."""

    vep_id: str
    source: str
    vc_translation_source: str
    conseq_translation_source: str
    db_info: dict[str, VepDbInfoDoc]
    variant_class_translations: dict[str, VepVariantClassDoc]
    conseq_translations: dict[str, VepConsequenceDoc]
    consequence_groups: dict[str, list[str]]
    consequence_diagram: VepConsequenceDiagramDoc | None = None


class PublicAssayCatalogImportRequest(BaseModel):
    """JSON document uploaded into the center public assay catalog."""

    model_config = ConfigDict(extra="forbid")
    document: dict[str, Any]


class PublicAssayCatalogUpdateRequest(BaseModel):
    """Catalog replacement content qualified by the expected revision."""

    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    catalog: dict[str, Any]


class PublicAssayCatalogTransitionRequest(BaseModel):
    """Revision-qualified catalog transition with assignment and decision details."""

    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    assignee: str = ""
    approve: bool = True
    reason: str = ""


class PublicAssayCatalogPresets(BaseModel):
    """Authoring choices shared across the catalog and scoped to each omics layer."""

    analysis: list[str]
    analysis_by_omics: dict[str, list[str]]
    input_material: list[str]
    sample_modes: list[str]


class PublicAssayCatalogAdminPayload(BaseModel):
    """Admin response containing the canonical catalog document."""

    catalog: PublicAssayCatalogDoc
    sources: dict[str, list[dict[str, Any]]]
    has_published: bool
    items: list[dict[str, Any]]
    reviewers: list[dict[str, str]]
    publishers: list[dict[str, str]]
    presets: PublicAssayCatalogPresets


class PublicAssayCatalogRevisionsPayload(BaseModel):
    """Public catalog audit revisions returned to administrators."""

    items: list[PublicCatalogRevisionDoc]


class PublicGenelistViewPayload(BaseModel):
    """Represent the public genelist view payload."""

    genelist: dict[str, Any]
    selected_assay: str | None = None
    filtered_genes: list[str]
    germline_genes: list[str]
    is_public: bool
    gene_markers: dict[str, dict[str, Any]] = {}


class PublicAspGenesPayload(BaseModel):
    """Represent the public asp genes payload."""

    asp_id: str
    asp: dict[str, Any] = {}
    catalog: dict[str, Any] = {}
    stats: dict[str, Any] = {}
    gene_details: list[dict[str, Any]]
    germline_gene_symbols: list[str]


class PublicGeneSymbolsPayload(BaseModel):
    """Represent the public gene symbols payload."""

    gene_symbols: list[str]


class PublicModuleAvailability(BaseModel):
    """Represent effective availability for one application module."""

    label: str
    description: str
    enabled: bool


class PublicTieringAvailability(BaseModel):
    """Represent effective tier-mutation availability by finding type."""

    small_variant: bool
    cnv: bool
    fusion: bool
    translocation: bool


class PublicCurationAvailability(BaseModel):
    """Represent non-sensitive runtime controls for clinical curation."""

    tiering: PublicTieringAvailability


class PublicModulesPayload(BaseModel):
    """Represent public application-module availability."""

    modules: dict[str, PublicModuleAvailability]
    curation: PublicCurationAvailability


class PublicAssayCatalogMatrixPayload(BaseModel):
    """Represent the public assay catalog matrix payload."""

    modalities: dict[str, Any]
    order: list[str]
    columns: list[dict[str, Any]]
    mod_spans: dict[str, int]
    cat_spans: dict[str, int]
    genes: list[str]
    matrix: dict[str, Any]
    gene_markers: dict[str, dict[str, Any]] = {}
    page: int = 1
    per_page: int = 100
    total: int = 0
    search: str | None = None
    has_next: bool = False
    has_previous: bool = False


class PublicAssayCatalogPayload(BaseModel):
    """Represent the public assay catalog payload."""

    meta: dict[str, Any]
    order: list[str]
    modalities: dict[str, Any]
    selected_mod: str | None = None
    categories: list[dict[str, Any]]
    selected_cat: str | None = None
    selected_isgl: str | None = None
    right: dict[str, Any]
    gene_mode: str
    genes: list[dict[str, Any]]
    stats: dict[str, Any]


class PublicAssayCatalogGenesCsvPayload(BaseModel):
    """Represent the public assay catalog genes csv payload."""

    filename: str
    content: str


class PublicFilterFlagMetadataPayload(BaseModel):
    """Represent center-configurable filter flag metadata."""

    exact: dict[str, Any]
    prefixes: dict[str, Any]
    terms: dict[str, Any]
    callers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    caller_options: dict[str, list[str]] = Field(default_factory=dict)


class PublicKnowledgebaseStatusPayload(BaseModel):
    """Represent sanitized installed knowledgebase release metadata."""

    releases: list[dict[str, Any]]
    summary: dict[str, Any]
