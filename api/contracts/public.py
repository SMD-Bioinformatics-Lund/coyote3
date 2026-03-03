"""Public route API contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PublicGenelistViewPayload(BaseModel):
    genelist: dict[str, Any]
    selected_assay: str | None = None
    filtered_genes: list[str]
    germline_genes: list[str]
    is_public: bool


class PublicAspGenesPayload(BaseModel):
    asp_id: str
    gene_details: list[dict[str, Any]]
    germline_gene_symbols: list[str]


class PublicGeneSymbolsPayload(BaseModel):
    gene_symbols: list[str]


class PublicAssayCatalogMatrixPayload(BaseModel):
    modalities: dict[str, Any]
    order: list[str]
    columns: list[dict[str, Any]]
    mod_spans: dict[str, int]
    cat_spans: dict[str, int]
    genes: list[str]
    matrix: dict[str, Any]


class PublicAssayCatalogPayload(BaseModel):
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
    filename: str
    content: str
