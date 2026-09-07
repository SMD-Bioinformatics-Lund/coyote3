#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
Public routes for the Coyote3 application.

These routes provide access to public-facing genomic data views, including genelist display,
genepanel matrix visualization, and gene explorer asp for public assays.
"""

from __future__ import annotations
from flask import current_app as app
from flask import (
    redirect,
    render_template,
    request,
    flash,
    send_file,
    abort,
)
import io
import csv
import datetime
from werkzeug import Response
from coyote.extensions import store, util
from coyote.blueprints.public import public_bp, filters
from copy import deepcopy
from collections import defaultdict


@public_bp.route("/genelists/<genelist_id>/view", methods=["GET"])
def view_genelist(genelist_id: str) -> Response | str:
    """
    Display a specific genelist and optionally filter its genes by a selected assay.

    Retrieves the genelist identified by `genelist_id` from the data store. If the genelist does not exist,
    logs an info message, flashes an error, and redirects to the current page.

    If an assay is selected via the "assay" query parameter, and it exists in the genelist's assays,
    filters the genes to include only those covered by the selected panel, unless the panel technology is "WGS",
    in which case all genes are shown. Also retrieves germline genes for the selected panel if available.

    Renders the `genelists/view_genelist.html` template with the genelist, selected assay, filtered genes,
    germline genes, and a flag indicating the view is public.

    Args:
        genelist_id (str): The unique identifier for the genelist to view.

    Returns:
        flask.Response | str: The rendered template or a redirect response if the genelist is not found.
    """
    genelist = store.isgl_handler.get_isgl(genelist_id, is_active=True)

    if not genelist:
        app.public_logger.info(
            f"Genelist '{genelist_id}' not found!",
            extra={"genelist_id": genelist_id},
        )
        flash(f"Genelist '{genelist_id}' not found!", "red")
        return redirect(request.url)

    selected_assay = request.args.get("assay")

    all_genes = genelist.get("genes", [])
    assays = genelist.get("assays", [])

    filtered_genes = all_genes
    germline_genes = []
    if selected_assay and selected_assay in assays:
        panel = store.asp_handler.get_asp(selected_assay)
        panel_genes = panel.get("covered_genes", []) if panel else []
        germline_genes = panel.get("germline_genes", []) if panel else []
        filtered_genes = (
            sorted(set(all_genes).intersection(panel_genes))
            if panel.get("asp_family") not in ["WGS", "WTS"]
            else all_genes
        )

    return render_template(
        "isgl/view_isgl.html",
        genelist=genelist,
        selected_assay=selected_assay,
        filtered_genes=filtered_genes,
        germline_genes=germline_genes,
        is_public=True,
    )


@public_bp.route("/asp/genes/<asp_id>")
def asp_genes(asp_id: str) -> str:
    """
    Display genes for a specific public assay panel.

    Retrieves the genes associated with the specified public assay panel ID and renders them in the 'asp_genes.html' template.

    Args:
        asp_id (str): The ID of the public assay panel.

    Returns:
        str: Rendered HTML page showing the genes for the specified public assay panel.
    """
    gene_symbols, germline_gene_symbols = store.asp_handler.get_asp_genes(asp_id)
    gene_details = store.hgnc_handler.get_metadata_by_symbols(gene_symbols)

    return render_template(
        "asp_genes.html",
        asp_id=asp_id,
        gene_details=gene_details,
        germline_gene_symbols=germline_gene_symbols,
    )


@public_bp.route("/assay-catalog-matrix")
def assay_catalog_matrix():
    """
    Gene × (modality → category → ISGL) matrix.

    - X-axis hierarchy: modality -> category -> genelist (ISGL)
    - Y-axis: gene symbol (string)
    - Cell: True/False (gene present in that ISGL/assay column)
    - If asp_id exists and equals the genelist key: use assay covered genes instead of ISGL.
    - Modalities/categories without gene lists still get a placeholder column so services are visible.
    """

    catalog = util.public.load_catalog()
    modalities = catalog.get("modalities") or {}
    order = util.public.modalities_order() or list(modalities.keys())

    # flat leaf columns
    columns: list[dict] = []  # each: {mod, cat, isgl_key, isgl_label, placeholder: bool}

    # colspans for headers
    mod_spans: dict[str, int] = defaultdict(int)  # modality -> total leaf columns
    cat_spans: dict[str, int] = {}  # f"{mod}::{cat}" -> leaf columns

    # matrix data
    all_genes: set[str] = set()  # all gene symbols
    matrix: dict[str, dict] = {}  # gene -> mod -> cat -> isgl_key -> bool

    # helper: get gene symbols from ASP via resolve_gene_table
    def fetch_asp_genes(asp_id: str) -> set[str]:
        """
        Use util.public.resolve_gene_table to get the ASP's covered genes,
        then extract gene symbols (hgnc_symbol).
        """
        try:
            gene_mode, gene_objs, stats = util.public.resolve_gene_table(asp_id, None)
        except Exception:
            return set()

        symbols: set[str] = set()
        if not gene_objs:
            return symbols

        for g in gene_objs:
            sym = None
            if isinstance(g, dict):
                sym = g.get("hgnc_symbol") or g.get("symbol") or g.get("gene_symbol")
            else:
                sym = getattr(g, "hgnc_symbol", None) or getattr(g, "symbol", None)
            if sym:
                symbols.add(sym)
        return symbols

    # main loop: build columns + spans + matrix
    for mod_key in order:
        mod_data = modalities.get(mod_key) or {}
        categories = mod_data.get("categories") or {}

        modality_total = 0  # leaf columns under this modality

        for cat_key, cat_data in categories.items():
            asp_id = cat_data.get("asp_id")  # may be None
            gene_lists = cat_data.get("gene_lists") or []

            # only count real genelists with non-empty key
            real_lists = [gl for gl in gene_lists if gl.get("key")]

            # CATEGORY WITH NO REAL GENE LISTS → placeholder column
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

            # CATEGORY WITH REAL GENE LISTS
            cat_spans[f"{mod_key}::{cat_key}"] = len(real_lists)
            modality_total += len(real_lists)

            for gl in real_lists:
                isgl_key = gl["key"]
                isgl_label = gl.get("label") or isgl_key

                # Decide which genes to use for this column
                # 1) If asp_id exists and matches this genelist key → use ASP covered genes
                # 2) Else → use ISGL genes from DB
                if asp_id and asp_id == isgl_key or isgl_key == "single_gene":
                    genes_here = fetch_asp_genes(asp_id)
                else:
                    isgl_doc = store.isgl_handler.get_isgl(isgl_key, is_active=True, is_public=True)
                    genes_here = set(isgl_doc.get("genes") or []) if isgl_doc else set()

                # Append leaf column
                columns.append(
                    {
                        "mod": mod_key,
                        "cat": cat_key,
                        "isgl_key": isgl_key,
                        "isgl_label": isgl_label,
                        "placeholder": False,
                    }
                )

                # Update global gene set + matrix
                all_genes |= genes_here
                for gene in genes_here:
                    matrix.setdefault(gene, {}).setdefault(mod_key, {}).setdefault(cat_key, {})[
                        isgl_key
                    ] = True

        # MODALITY WITH NO CATEGORIES OR NO GENE LISTS AT ALL → modality-level placeholder
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

    # ensure all missing cells are False
    for gene in all_genes:
        for col in columns:
            mod_key = col["mod"]
            cat_key = col["cat"]
            isgl_key = col["isgl_key"]

            matrix.setdefault(gene, {}).setdefault(mod_key, {}).setdefault(cat_key, {}).setdefault(
                isgl_key, False
            )

    genes_sorted = sorted(all_genes)

    vm = {
        "modalities": modalities,
        "order": order,
        "columns": columns,  # flat leaf columns in order
        "mod_spans": mod_spans,
        "cat_spans": cat_spans,
        "genes": genes_sorted,
        "matrix": matrix,
    }
    return render_template("assay_catalog_matrix.html", **vm)


@public_bp.route("/assay-catalog")
@public_bp.route("/assay-catalog/<mod>")
@public_bp.route("/assay-catalog/<mod>/<cat>")
@public_bp.route("/assay-catalog/<mod>/<cat>/isgl/<isgl_key>")
def assay_catalog(mod: str | None = None, cat: str | None = None, isgl_key: str | None = None):
    """
    Display the assay catalog with modalities, categories, and gene lists.

    Args:
        mod (str | None): The modality identifier from the URL, or None for the top-level view.
        cat (str | None): The category identifier from the URL, or None for modality/top-level view.
        isgl_key (str | None): The in-silico genelist key from the URL, or None for modality/category view.

    Returns:
        flask.Response: The rendered HTML page for the assay catalog, or a 404 error if not found.
    """
    catalog = util.public.load_catalog()
    order = util.public.modalities_order()
    if not order:
        abort(404)

    # level detection
    selected_mod = util.public.normalize_mod(mod) if mod else None
    selected_cat = cat if cat else None
    selected_isgl = isgl_key if isgl_key else None

    # left tree data
    mods = catalog.get("modalities") or {}

    # right pane data by level
    if not selected_mod:
        # top level: only modalities visible; right shows generic landing (from catalog meta)
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
        # modality level: show modality description; inherit missing fields from first category
        right = util.public.hydrate_modality(selected_mod)
        gene_mode, genes, stats = util.public.resolve_gene_table(right.get("asp_id"), None)
    else:
        # category / genelist level
        if selected_isgl:
            hc = util.public.hydrate_category(
                selected_mod, selected_cat, selected_isgl, env="production"
            )
        else:
            hc = util.public.hydrate_category(selected_mod, selected_cat, env="production")
        if not hc:
            abort(404)
        right = {
            "title": hc.get("label"),
            "description": hc.get("description"),
            "input_material": hc.get("input_material"),
            "tat": hc.get("tat"),
            "sample_modes": hc.get("sample_modes") or [],
            "analysis": hc.get("analysis") or [],
            "asp_id": hc.get("asp_id"),
            "asp": hc.get("asp"),
            "gene_lists": hc.get("gene_lists") or [],
        }
        gene_mode, genes, stats = util.public.resolve_gene_table(hc.get("asp_id"), selected_isgl)

    # Add Drug information
    genes = util.public.apply_drug_info(genes=deepcopy(genes), druglist_name="Drug_Addon")

    # view model
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
        "categories": util.public.categories_for(selected_mod) if selected_mod else [],
        "selected_cat": selected_cat,
        "selected_isgl": selected_isgl,
        "right": right,
        "gene_mode": gene_mode,
        "genes": genes,
        "stats": stats,
    }
    return render_template("assay_catalog.html", **vm)


# ---- CSV export for the visible table ----
@public_bp.route("/assay-catalog/<mod>/genes.csv")
@public_bp.route("/assay-catalog/<mod>/<cat>/genes.csv")
@public_bp.route("/assay-catalog/<mod>/<cat>/isgl/<isgl_key>/genes.csv")
def assay_catalog_genes_csv(mod: str, cat: str | None = None, isgl_key: str | None = None):
    """
    Export genes from the assay catalog as a CSV file.

    Args:
        mod (str): The modality identifier from the URL.
        cat (str | None, optional): The category identifier from the URL. Defaults to None.
        isgl_key (str | None, optional): The in-silico genelist key from the URL. Defaults to None.

    Returns:
        flask.Response: A CSV file containing gene data for the selected modality, category, and/or genelist.
    """
    selected_mod = util.public.normalize_mod(mod)
    if not selected_mod:
        abort(404)

    # Resolve asp + table according to level
    if not cat:
        right = util.public.hydrate_modality(selected_mod, env="production")
        asp_id = right.get("asp_id")
    else:
        hc = util.public.hydrate_category(selected_mod, cat, env="production")
        if not hc:
            abort(404)
        asp_id = hc.get("asp_id")

    mode, rows, _ = util.public.resolve_gene_table(asp_id, isgl_key)

    sio = io.StringIO()
    w = csv.writer(sio, lineterminator="\n")
    w.writerow(["HGNC_ID", "Gene_Symbol", "Chromosome", "Start", "End", "Gene_Type", "Drug Target"])
    for g in rows:
        w.writerow(
            [
                (g.get("hgnc_id") or "").replace("HGNC:", "HGNC:"),
                g.get("hgnc_symbol") or g.get("symbol") or "",
                g.get("chromosome") or "",
                g.get("start") or "",
                g.get("end") or "",
                ",".join(g.get("gene_type") or []),
                g.get("drug_target") or "",
            ]
        )
    buf = io.BytesIO(sio.getvalue().encode("utf-8"))
    dt = datetime.date.today().isoformat()
    if not cat:
        label = f"{selected_mod}.{mode if not isgl_key else f'isgl-{isgl_key}'}"
    else:
        label = f"{selected_mod}.{cat}.{mode if not isgl_key else f'isgl-{isgl_key}'}"
    fname = f"{label}.{dt}.genes.csv"
    return send_file(buf, mimetype="text/csv", as_attachment=True, download_name=fname)


@public_bp.route("/assay-catalog/genes/<isgl_key>/view")
def assay_catalog_isgl_genes_view(isgl_key: str | None = None) -> str:
    """ """
    isgl = store.isgl_handler.get_isgl(isgl_key) or {}
    gene_symbols = set(sorted(isgl.get("genes", []))) if isgl_key else set()

    return render_template(
        "genes.html",
        gene_symbols=gene_symbols,
    )


@public_bp.route("/contact")
def contact() -> str:
    """
    Displays the contact information page.

    Returns:
        str: Rendered HTML page containing contact details.
    """
    contact = app.config.get("CONTACT") or {}
    return render_template("contact.html", contact=contact)
