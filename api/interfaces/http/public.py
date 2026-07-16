"""Canonical public router module."""

from __future__ import annotations

import csv
import datetime
import io
from copy import deepcopy
from pathlib import Path

import yaml
from fastapi import APIRouter, Query

from api.app.container import util
from api.app.deps.services import get_public_catalog_service
from api.app.http import api_error as _api_error
from api.application.public.catalog import PublicCatalogService
from api.config.app_config import REPO_ROOT
from api.contracts.public import (
    PublicAspGenesPayload,
    PublicAssayCatalogGenesCsvPayload,
    PublicAssayCatalogMatrixPayload,
    PublicAssayCatalogPayload,
    PublicFilterFlagMetadataPayload,
    PublicGenelistViewPayload,
    PublicGeneSymbolsPayload,
)

router = APIRouter(tags=["public"])
__all__ = ["router", "PublicCatalogService"]


def _load_filter_flag_metadata() -> dict:
    metadata_path = Path(REPO_ROOT) / "api" / "data" / "filter_flag_metadata.yaml"
    if not metadata_path.exists():
        return {"exact": {}, "prefixes": {}, "terms": {}}
    with metadata_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return {
        "exact": raw.get("exact") or {},
        "prefixes": raw.get("prefixes") or {},
        "terms": raw.get("terms") or {},
    }


@router.get("/api/v1/public/filter-flags/metadata", response_model=PublicFilterFlagMetadataPayload)
def public_filter_flag_metadata_read():
    """Return center-configurable VCF filter flag metadata."""
    return util.common.convert_to_serializable(_load_filter_flag_metadata())


@router.get(
    "/api/v1/public/genelists/{genelist_id}/view_context", response_model=PublicGenelistViewPayload
)
def public_genelist_view_context_read(genelist_id: str, assay: str | None = None):
    """Return public view context for a genelist.

    Args:
        genelist_id: Genelist identifier to inspect.
        assay: Optional assay used to scope visible genes.

    Returns:
        dict: Public genelist view payload.
    """
    service = get_public_catalog_service()
    payload = service.genelist_view_context(genelist_id, assay)
    if not payload:
        raise _api_error(404, "Genelist not found")
    return util.common.convert_to_serializable(payload)


@router.get("/api/v1/public/asp/{asp_id}/genes", response_model=PublicAspGenesPayload)
def public_asp_genes_read(asp_id: str):
    """Return public genes for an assay panel.

    Args:
        asp_id: Assay-panel identifier to inspect.

    Returns:
        dict: Public assay-panel gene payload.
    """
    service = get_public_catalog_service()
    return util.common.convert_to_serializable(service.asp_genes_payload(asp_id))


@router.get(
    "/api/v1/public/assay-catalog/genes/{isgl_key}/view_context",
    response_model=PublicGeneSymbolsPayload,
)
def public_assay_catalog_isgl_genes_view_read(isgl_key: str):
    """Return public catalog genes for a catalog genelist.

    Args:
        isgl_key: Catalog genelist identifier to inspect.

    Returns:
        dict: Public gene-symbol payload.
    """
    service = get_public_catalog_service()
    return util.common.convert_to_serializable(service.assay_catalog_gene_symbols_payload(isgl_key))


@router.get(
    "/api/v1/public/assay-catalog-matrix/context", response_model=PublicAssayCatalogMatrixPayload
)
def public_assay_catalog_matrix_context_read(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
    gene: str | None = None,
):
    """Return the public assay-catalog matrix payload.

    Returns:
        dict: Assay-catalog matrix payload.
    """
    service = get_public_catalog_service()
    vm = service.assay_catalog_matrix_payload(page=page, per_page=per_page, gene=gene)
    return util.common.convert_to_serializable(vm)


@router.get("/api/v1/public/assay-catalog/context", response_model=PublicAssayCatalogPayload)
def public_assay_catalog_context_read(
    mod: str | None = None,
    cat: str | None = None,
    isgl_key: str | None = None,
):
    """Return public assay-catalog context for the selected modality/category."""
    service = get_public_catalog_service()
    catalog = service.load_catalog()
    order = service.modalities_order()
    if not order:
        raise _api_error(404, "Catalog not found")

    selected_mod = service.normalize_mod(mod) if mod else None
    selected_cat = cat if cat else None
    selected_isgl = isgl_key if isgl_key else None
    mods = catalog.get("modalities") or {}

    if not selected_mod:
        right = {
            "title": catalog.get("header") or "Assay Catalog",
            "description": catalog.get("description")
            or "Select a modality to explore available assays.",
            "input_material": None,
            "tat": None,
            "sample_modes": [],
            "analysis": [],
            "report_sections": [],
            "asp_id": None,
            "aspc_id": None,
            "aspc_ids": {},
            "subpanel_id": None,
            "asp": None,
            "clinical_indications": [],
            "limitations": None,
            "public_notes": None,
            "gene_lists": [],
        }
        gene_mode, genes, stats = (
            "covered",
            [],
            {"total": 0, "covered_total": 0, "germline_total": 0},
        )
    elif selected_mod and not selected_cat:
        right = service.hydrate_modality(selected_mod)
        gene_mode, genes, stats = service.resolve_gene_table(right.get("asp_id"), None)
    else:
        if selected_isgl:
            hydrated_cat = service.hydrate_category(
                selected_mod, selected_cat, selected_isgl, env="production"
            )
        else:
            hydrated_cat = service.hydrate_category(selected_mod, selected_cat, env="production")
        if not hydrated_cat:
            raise _api_error(404, "Category not found")
        right = {
            "title": hydrated_cat.get("title") or hydrated_cat.get("label"),
            "catalog_id": hydrated_cat.get("catalog_id"),
            "subheading": hydrated_cat.get("subheading"),
            "description": hydrated_cat.get("description"),
            "input_material": hydrated_cat.get("input_material"),
            "tat": hydrated_cat.get("tat"),
            "sample_modes": hydrated_cat.get("sample_modes") or [],
            "analysis": hydrated_cat.get("analysis") or [],
            "report_sections": hydrated_cat.get("report_sections") or [],
            "asp_id": hydrated_cat.get("asp_id"),
            "aspc_id": hydrated_cat.get("aspc_id"),
            "aspc_ids": hydrated_cat.get("aspc_ids") or {},
            "subpanel_id": hydrated_cat.get("subpanel_id"),
            "asp": hydrated_cat.get("asp"),
            "clinical_indications": hydrated_cat.get("clinical_indications") or [],
            "limitations": hydrated_cat.get("limitations"),
            "public_notes": hydrated_cat.get("public_notes"),
            "gene_lists": hydrated_cat.get("gene_lists") or [],
            "sample_query": hydrated_cat.get("sample_query"),
        }
        gene_mode, genes, stats = service.resolve_gene_table(
            hydrated_cat.get("asp_id"), selected_isgl
        )

    genes = service.apply_drug_info(genes=deepcopy(genes), druglist_name="drug_addon")
    vm = {
        "meta": {
            "version": catalog.get("version"),
            "last_updated": catalog.get("last_updated"),
            "maintainer": catalog.get("maintainer"),
            "header": catalog.get("header"),
            "description": catalog.get("description"),
            "nav_groups": catalog.get("nav_groups") or [],
        },
        "order": order,
        "modalities": mods,
        "selected_mod": selected_mod,
        "categories": service.categories_for(selected_mod) if selected_mod else [],
        "selected_cat": selected_cat,
        "selected_isgl": selected_isgl,
        "right": right,
        "gene_mode": gene_mode,
        "genes": genes,
        "stats": stats,
    }
    return util.common.convert_to_serializable(vm)


@router.get(
    "/api/v1/public/assay-catalog/genes.csv/context",
    response_model=PublicAssayCatalogGenesCsvPayload,
)
def public_assay_catalog_genes_csv_context_read(
    mod: str,
    cat: str | None = None,
    isgl_key: str | None = None,
):
    """Return a CSV export payload for public assay-catalog genes."""
    service = get_public_catalog_service()
    selected_mod = service.normalize_mod(mod)
    if not selected_mod:
        raise _api_error(404, "Modality not found")

    if not cat:
        right = service.hydrate_modality(selected_mod)
        asp_id = right.get("asp_id")
    else:
        hydrated_cat = service.hydrate_category(selected_mod, cat, env="production")
        if not hydrated_cat:
            raise _api_error(404, "Category not found")
        asp_id = hydrated_cat.get("asp_id")

    mode, rows, _stats = service.resolve_gene_table(asp_id, isgl_key)

    sio = io.StringIO()
    writer = csv.writer(sio, lineterminator="\n")
    writer.writerow(
        ["HGNC_ID", "Gene_Symbol", "Chromosome", "Start", "End", "Gene_Type", "Drug Target"]
    )
    for gene in rows:
        writer.writerow(
            [
                (gene.get("hgnc_id") or "").replace("HGNC:", "HGNC:"),
                gene.get("hgnc_symbol") or gene.get("symbol") or "",
                gene.get("chromosome") or "",
                gene.get("start") or "",
                gene.get("end") or "",
                ",".join(gene.get("gene_type") or []),
                gene.get("drug_target") or "",
            ]
        )
    dt = datetime.date.today().isoformat()
    if not cat:
        label = f"{selected_mod}.{mode if not isgl_key else f'isgl-{isgl_key}'}"
    else:
        label = f"{selected_mod}.{cat}.{mode if not isgl_key else f'isgl-{isgl_key}'}"
    fname = f"{label}.{dt}.genes.csv"
    return {"filename": fname, "content": sio.getvalue()}
