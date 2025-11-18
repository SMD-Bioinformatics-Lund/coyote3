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


@public_bp.route("/genepanel-matrix", methods=["GET"])
def genepanel_matrix() -> str:
    """
    Render a matrix view of all active in-silico genelists and their associated assays, grouped by public assay labels.

    Fetches all active in-silico genelists from the data store and organizes their assays using the public assay mapping
    from the application configuration. Passes this grouped data to the 'genepanel_matrix.html' template for display.

    Returns:
        str: Rendered HTML page showing the genelist-to-assay matrix.
    """
    genelists = store.isgl_handler.get_all_isgl(is_active=True, is_public=True, adhoc=False)
    public_assay_map = app.config["PUBLIC_ASSAY_MAP"]

    return render_template(
        "genepanel_matrix.html",
        genelists=genelists,
        assay_grouped=public_assay_map,
    )


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
        print(f"ASP_ID: {right.get('asp_id')}")
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
