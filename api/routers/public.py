"""Canonical public router module."""

from __future__ import annotations

import csv
import datetime
import io
from collections import defaultdict
from copy import deepcopy

from fastapi import APIRouter

from api.contracts.public import (
    PublicAspGenesPayload,
    PublicAssayCatalogGenesCsvPayload,
    PublicAssayCatalogMatrixPayload,
    PublicAssayCatalogPayload,
    PublicGeneSymbolsPayload,
    PublicGenelistViewPayload,
)
from api.core.public.catalog import PublicCatalogService
from api.extensions import util
from api.http import api_error as _api_error
from api.repositories.public_repository import PublicCatalogRepository as MongoPublicCatalogRepository

router = APIRouter(tags=["public"])

if not hasattr(util, "common"):
    util.init_util()


def _catalog_service() -> type[PublicCatalogService]:
    """Handle  catalog service.

    Returns:
            The  catalog service result.
    """
    if not PublicCatalogService.has_repository():
        PublicCatalogService.set_repository(MongoPublicCatalogRepository())
    return PublicCatalogService


@router.get("/api/v1/public/genelists/{genelist_id}/view_context", response_model=PublicGenelistViewPayload)
def public_genelist_view_context_read(genelist_id: str, assay: str | None = None):
    """Handle public genelist view context read.

    Args:
        genelist_id (str): Value for ``genelist_id``.
        assay (str | None): Value for ``assay``.

    Returns:
        The function result.
    """
    service = _catalog_service()
    payload = service.genelist_view_context(genelist_id, assay)
    if not payload:
        raise _api_error(404, "Genelist not found")
    return util.common.convert_to_serializable(payload)


@router.get("/api/v1/public/asp/{asp_id}/genes", response_model=PublicAspGenesPayload)
def public_asp_genes_read(asp_id: str):
    """Handle public asp genes read.

    Args:
        asp_id (str): Value for ``asp_id``.

    Returns:
        The function result.
    """
    service = _catalog_service()
    return util.common.convert_to_serializable(service.asp_genes_payload(asp_id))


@router.get(
    "/api/v1/public/assay-catalog/genes/{isgl_key}/view_context",
    response_model=PublicGeneSymbolsPayload,
)
def public_assay_catalog_isgl_genes_view_read(isgl_key: str):
    """Handle public assay catalog isgl genes view read.

    Args:
        isgl_key (str): Value for ``isgl_key``.

    Returns:
        The function result.
    """
    service = _catalog_service()
    return util.common.convert_to_serializable(service.assay_catalog_gene_symbols_payload(isgl_key))


@router.get("/api/v1/public/assay-catalog-matrix/context", response_model=PublicAssayCatalogMatrixPayload)
def public_assay_catalog_matrix_context_read():
    """Handle public assay catalog matrix context read.

    Returns:
        The function result.
    """
    service = _catalog_service()
    catalog = service.load_catalog()
    modalities = catalog.get("modalities") or {}
    order = service.modalities_order() or list(modalities.keys())

    columns: list[dict] = []
    mod_spans: dict[str, int] = defaultdict(int)
    cat_spans: dict[str, int] = {}
    all_genes: set[str] = set()
    matrix: dict[str, dict] = {}

    def fetch_asp_genes(asp_id: str) -> set[str]:
        """Fetch asp genes.

        Args:
            asp_id (str): Value for ``asp_id``.

        Returns:
            set[str]: The function result.
        """
        try:
            _gene_mode, gene_objs, _stats = service.resolve_gene_table(asp_id, None)
        except Exception:
            return set()
        symbols: set[str] = set()
        for gene_obj in gene_objs or []:
            if isinstance(gene_obj, dict):
                sym = gene_obj.get("hgnc_symbol") or gene_obj.get("symbol") or gene_obj.get("gene_symbol")
            else:
                sym = getattr(gene_obj, "hgnc_symbol", None) or getattr(gene_obj, "symbol", None)
            if sym:
                symbols.add(sym)
        return symbols

    for mod_key in order:
        mod_data = modalities.get(mod_key) or {}
        categories = mod_data.get("categories") or {}
        modality_total = 0

        for cat_key, cat_data in categories.items():
            asp_id = cat_data.get("asp_id")
            gene_lists = cat_data.get("gene_lists") or []
            real_lists = [gl for gl in gene_lists if gl.get("key")]

            if not real_lists:
                cat_spans[f"{mod_key}::{cat_key}"] = 1
                modality_total += 1
                columns.append(
                    {
                        "mod": mod_key,
                        "cat": cat_key,
                        "isgl_key": f"__none__::{mod_key}::{cat_key}",
                        "isgl_label": "-",
                        "placeholder": True,
                    }
                )
                continue

            cat_spans[f"{mod_key}::{cat_key}"] = len(real_lists)
            modality_total += len(real_lists)

            for gl in real_lists:
                isgl_key = gl["key"]
                isgl_label = gl.get("label") or isgl_key
                if (asp_id and asp_id == isgl_key) or isgl_key == "single_gene":
                    genes_here = fetch_asp_genes(asp_id)
                else:
                    genes_here = service.isgl_genes_for_matrix(isgl_key)

                columns.append(
                    {
                        "mod": mod_key,
                        "cat": cat_key,
                        "isgl_key": isgl_key,
                        "isgl_label": isgl_label,
                        "placeholder": False,
                    }
                )
                all_genes |= genes_here
                for gene in genes_here:
                    matrix.setdefault(gene, {}).setdefault(mod_key, {}).setdefault(cat_key, {})[isgl_key] = True

        if not categories and modality_total == 0:
            placeholder_key = f"__none__::{mod_key}"
            columns.append(
                {
                    "mod": mod_key,
                    "cat": "__none__",
                    "isgl_key": placeholder_key,
                    "isgl_label": "-",
                    "placeholder": True,
                }
            )
            mod_spans[mod_key] = 1
            cat_spans[f"{mod_key}::__none__"] = 1
        else:
            mod_spans[mod_key] = modality_total if modality_total > 0 else 1

    for gene in all_genes:
        for col in columns:
            mod_key = col["mod"]
            cat_key = col["cat"]
            isgl_key = col["isgl_key"]
            matrix.setdefault(gene, {}).setdefault(mod_key, {}).setdefault(cat_key, {}).setdefault(isgl_key, False)

    vm = {
        "modalities": modalities,
        "order": order,
        "columns": columns,
        "mod_spans": mod_spans,
        "cat_spans": cat_spans,
        "genes": sorted(all_genes),
        "matrix": matrix,
    }
    return util.common.convert_to_serializable(vm)


@router.get("/api/v1/public/assay-catalog/context", response_model=PublicAssayCatalogPayload)
def public_assay_catalog_context_read(
    mod: str | None = None,
    cat: str | None = None,
    isgl_key: str | None = None,
):
    """Handle public assay catalog context read.

    Args:
        mod (str | None): Value for ``mod``.
        cat (str | None): Value for ``cat``.
        isgl_key (str | None): Value for ``isgl_key``.

    Returns:
        The function result.
    """
    service = _catalog_service()
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
            "title": "Assay Catalog",
            "description": "Select a modality to explore available assays.",
            "input_material": None,
            "tat": None,
            "sample_modes": [],
            "analysis": [],
            "asp_id": None,
            "asp": None,
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
            hydrated_cat = service.hydrate_category(selected_mod, selected_cat, selected_isgl, env="production")
        else:
            hydrated_cat = service.hydrate_category(selected_mod, selected_cat, env="production")
        if not hydrated_cat:
            raise _api_error(404, "Category not found")
        right = {
            "title": hydrated_cat.get("label"),
            "description": hydrated_cat.get("description"),
            "input_material": hydrated_cat.get("input_material"),
            "tat": hydrated_cat.get("tat"),
            "sample_modes": hydrated_cat.get("sample_modes") or [],
            "analysis": hydrated_cat.get("analysis") or [],
            "asp_id": hydrated_cat.get("asp_id"),
            "asp": hydrated_cat.get("asp"),
            "gene_lists": hydrated_cat.get("gene_lists") or [],
        }
        gene_mode, genes, stats = service.resolve_gene_table(hydrated_cat.get("asp_id"), selected_isgl)

    genes = service.apply_drug_info(genes=deepcopy(genes), druglist_name="Drug_Addon")
    vm = {
        "meta": {
            "version": catalog.get("version"),
            "last_updated": catalog.get("last_updated"),
            "maintainer": catalog.get("maintainer"),
            "header": catalog.get("header"),
            "description": catalog.get("description"),
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
    """Handle public assay catalog genes csv context read.

    Args:
        mod (str): Value for ``mod``.
        cat (str | None): Value for ``cat``.
        isgl_key (str | None): Value for ``isgl_key``.

    Returns:
        The function result.
    """
    service = _catalog_service()
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
    writer.writerow(["HGNC_ID", "Gene_Symbol", "Chromosome", "Start", "End", "Gene_Type", "Drug Target"])
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
