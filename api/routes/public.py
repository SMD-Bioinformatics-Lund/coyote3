"""Public read routes for Flask public blueprint pages."""

from __future__ import annotations

import csv
import datetime
import io
from collections import defaultdict
from copy import deepcopy

from api.extensions import store, util
from api.app import _api_error, app, flask_app
from api.services.public_catalog import PublicCatalogService


@app.get("/api/v1/public/genelists/{genelist_id}/view_context")
def public_genelist_view_context_read(genelist_id: str, assay: str | None = None):
    genelist = store.isgl_handler.get_isgl(genelist_id, is_active=True)
    if not genelist:
        raise _api_error(404, "Genelist not found")

    selected_assay = assay
    all_genes = genelist.get("genes", [])
    assays = genelist.get("assays", [])

    filtered_genes = all_genes
    germline_genes: list[str] = []
    if selected_assay and selected_assay in assays:
        panel = store.asp_handler.get_asp(selected_assay)
        panel_genes = panel.get("covered_genes", []) if panel else []
        germline_genes = panel.get("germline_genes", []) if panel else []
        filtered_genes = (
            sorted(set(all_genes).intersection(panel_genes))
            if panel and panel.get("asp_family") not in ["WGS", "WTS"]
            else all_genes
        )

    return util.common.convert_to_serializable(
        {
            "genelist": genelist,
            "selected_assay": selected_assay,
            "filtered_genes": filtered_genes,
            "germline_genes": germline_genes,
            "is_public": True,
        }
    )


@app.get("/api/v1/public/asp/{asp_id}/genes")
def public_asp_genes_read(asp_id: str):
    gene_symbols, germline_gene_symbols = store.asp_handler.get_asp_genes(asp_id)
    gene_details = store.hgnc_handler.get_metadata_by_symbols(gene_symbols)
    return util.common.convert_to_serializable(
        {
            "asp_id": asp_id,
            "gene_details": gene_details,
            "germline_gene_symbols": germline_gene_symbols,
        }
    )


@app.get("/api/v1/public/assay-catalog/genes/{isgl_key}/view_context")
def public_assay_catalog_isgl_genes_view_read(isgl_key: str):
    isgl = store.isgl_handler.get_isgl(isgl_key) or {}
    gene_symbols = set(sorted(isgl.get("genes", []))) if isgl_key else set()
    return util.common.convert_to_serializable({"gene_symbols": sorted(gene_symbols)})


@app.get("/api/v1/public/assay-catalog-matrix/context")
def public_assay_catalog_matrix_context_read():
    with flask_app.app_context():
        catalog = PublicCatalogService.load_catalog()
        modalities = catalog.get("modalities") or {}
        order = PublicCatalogService.modalities_order() or list(modalities.keys())

        columns: list[dict] = []
        mod_spans: dict[str, int] = defaultdict(int)
        cat_spans: dict[str, int] = {}
        all_genes: set[str] = set()
        matrix: dict[str, dict] = {}

        def fetch_asp_genes(asp_id: str) -> set[str]:
            try:
                _gene_mode, gene_objs, _stats = PublicCatalogService.resolve_gene_table(asp_id, None)
            except Exception:
                return set()
            symbols: set[str] = set()
            for gene_obj in gene_objs or []:
                if isinstance(gene_obj, dict):
                    sym = (
                        gene_obj.get("hgnc_symbol")
                        or gene_obj.get("symbol")
                        or gene_obj.get("gene_symbol")
                    )
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
                            "isgl_label": "—",
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
                        isgl_doc = store.isgl_handler.get_isgl(isgl_key, is_active=True, is_public=True)
                        genes_here = set(isgl_doc.get("genes") or []) if isgl_doc else set()

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
                        matrix.setdefault(gene, {}).setdefault(mod_key, {}).setdefault(cat_key, {})[
                            isgl_key
                        ] = True

            if not categories and modality_total == 0:
                placeholder_key = f"__none__::{mod_key}"
                columns.append(
                    {
                        "mod": mod_key,
                        "cat": "__none__",
                        "isgl_key": placeholder_key,
                        "isgl_label": "—",
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
                matrix.setdefault(gene, {}).setdefault(mod_key, {}).setdefault(cat_key, {}).setdefault(
                    isgl_key, False
                )

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


@app.get("/api/v1/public/assay-catalog/context")
def public_assay_catalog_context_read(
    mod: str | None = None,
    cat: str | None = None,
    isgl_key: str | None = None,
):
    with flask_app.app_context():
        catalog = PublicCatalogService.load_catalog()
        order = PublicCatalogService.modalities_order()
        if not order:
            raise _api_error(404, "Catalog not found")

        selected_mod = PublicCatalogService.normalize_mod(mod) if mod else None
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
            right = PublicCatalogService.hydrate_modality(selected_mod)
            gene_mode, genes, stats = PublicCatalogService.resolve_gene_table(right.get("asp_id"), None)
        else:
            if selected_isgl:
                hydrated_cat = PublicCatalogService.hydrate_category(
                    selected_mod, selected_cat, selected_isgl, env="production"
                )
            else:
                hydrated_cat = PublicCatalogService.hydrate_category(
                    selected_mod, selected_cat, env="production"
                )
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
            gene_mode, genes, stats = PublicCatalogService.resolve_gene_table(
                hydrated_cat.get("asp_id"), selected_isgl
            )

        genes = PublicCatalogService.apply_drug_info(genes=deepcopy(genes), druglist_name="Drug_Addon")
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
            "categories": PublicCatalogService.categories_for(selected_mod) if selected_mod else [],
            "selected_cat": selected_cat,
            "selected_isgl": selected_isgl,
            "right": right,
            "gene_mode": gene_mode,
            "genes": genes,
            "stats": stats,
        }
        return util.common.convert_to_serializable(vm)


@app.get("/api/v1/public/assay-catalog/genes.csv/context")
def public_assay_catalog_genes_csv_context_read(
    mod: str,
    cat: str | None = None,
    isgl_key: str | None = None,
):
    with flask_app.app_context():
        selected_mod = PublicCatalogService.normalize_mod(mod)
        if not selected_mod:
            raise _api_error(404, "Modality not found")

        if not cat:
            right = PublicCatalogService.hydrate_modality(selected_mod)
            asp_id = right.get("asp_id")
        else:
            hydrated_cat = PublicCatalogService.hydrate_category(selected_mod, cat, env="production")
            if not hydrated_cat:
                raise _api_error(404, "Category not found")
            asp_id = hydrated_cat.get("asp_id")

        mode, rows, _stats = PublicCatalogService.resolve_gene_table(asp_id, isgl_key)

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
