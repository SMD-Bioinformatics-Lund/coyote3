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
from werkzeug import Response
from coyote.blueprints.public import public_bp
from coyote.integrations.api.api_client import ApiRequestError, get_web_api_client


@public_bp.route("/genelists/<genelist_id>/view", methods=["GET"])
def view_genelist(genelist_id: str) -> Response | str:
    """
    Display a specific genelist and optionally filter its genes by a selected assay.

    Retrieves the genelist identified by `genelist_id` through the API layer. If the genelist does not exist,
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
    selected_assay = request.args.get("assay")
    try:
        payload = get_web_api_client().get_public_genelist_view_context(
            genelist_id=genelist_id,
            selected_assay=selected_assay,
        )
    except ApiRequestError:
        app.public_logger.info(
            "Genelist '%s' not found via API",
            genelist_id,
            extra={"genelist_id": genelist_id},
        )
        flash(f"Genelist '{genelist_id}' not found!", "red")
        return redirect(request.url)

    return render_template(
        "isgl/view_isgl.html",
        genelist=payload.genelist,
        selected_assay=payload.selected_assay,
        filtered_genes=payload.filtered_genes,
        germline_genes=payload.germline_genes,
        is_public=payload.is_public,
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
    payload = get_web_api_client().get_public_asp_genes(asp_id=asp_id)

    return render_template(
        "asp_genes.html",
        asp_id=payload.asp_id,
        gene_details=payload.gene_details,
        germline_gene_symbols=payload.germline_gene_symbols,
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

    payload = get_web_api_client().get_public_assay_catalog_matrix_context()
    return render_template("assay_catalog_matrix.html", **payload.model_dump())


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
    try:
        payload = get_web_api_client().get_public_assay_catalog_context(
            mod=mod,
            cat=cat,
            isgl_key=isgl_key,
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            abort(404)
        raise
    return render_template("assay_catalog.html", **payload.model_dump())


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
    payload = get_web_api_client().get_public_assay_catalog_genes_csv_context(
        mod=mod,
        cat=cat,
        isgl_key=isgl_key,
    )
    buf = io.BytesIO(payload.content.encode("utf-8"))
    return send_file(buf, mimetype="text/csv", as_attachment=True, download_name=payload.filename)


@public_bp.route("/assay-catalog/genes/<isgl_key>/view")
def assay_catalog_isgl_genes_view(isgl_key: str | None = None) -> str:
    """ """
    if not isgl_key:
        return render_template("genes.html", gene_symbols=[])
    payload = get_web_api_client().get_public_assay_catalog_genes_view(isgl_key=isgl_key)

    return render_template(
        "genes.html",
        gene_symbols=payload.gene_symbols,
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
