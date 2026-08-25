"""Public route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PublicGenelistViewPayload(BaseModel):
    """Represent the public genelist view payload."""

    genelist: dict[str, Any]
    selected_assay: str | None = None
    filtered_genes: list[str]
    germline_genes: list[str]
    is_public: bool


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


class PublicContactPayload(BaseModel):
    """Represent center-owned public contact and support metadata."""

    organization: dict[str, Any]
    support: dict[str, Any]
    codebase: dict[str, Any] = {}
    contacts: list[dict[str, Any]]
    links: list[dict[str, Any]]
    hours: list[dict[str, Any]]
    meta: dict[str, Any] = {}


class PublicAboutPayload(PublicContactPayload):
    """Represent public application, organization, and reference metadata."""

    application: dict[str, Any]
    references: dict[str, Any]
    software: dict[str, Any]
    databases: dict[str, Any]
    software_links: list[dict[str, Any]] = []
