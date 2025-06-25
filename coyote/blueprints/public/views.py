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

from flask import current_app as app
from flask import (
    redirect,
    render_template,
    request,
    flash,
)

from werkzeug import Response
from coyote.extensions import store
from coyote.blueprints.public import public_bp


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
        "genelists/view_genelist.html",
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
    genelists = store.isgl_handler.get_all_isgl(is_active=True)
    public_assay_map = app.config["PUBLIC_ASSAY_MAP"]

    return render_template(
        "genepanel_matrix.html",
        genelists=genelists,
        assay_grouped=public_assay_map,
    )


@public_bp.route("/panel-gene-explorer")
def panel_gene_explorer() -> str:
    """
    Display the gene explorer panel for public assays.

    Handles selection of a panel and subpanel via query parameters, retrieves the corresponding subpanels and gene details, and renders the 'panel_gene_explorer.html' template.

    Query Parameters:
        panel (str, optional): Name of the selected public assay panel.
        subpanel (str, optional): Name of the selected subpanel.

    Returns:
        flask.Response: Rendered HTML template with context:
            - asp: List of available public assay panel names.
            - selected_panel_name: Name of the selected panel.
            - subpanels: List of subpanels for the selected panel.
            - selected_subpanel_name: Name of the selected subpanel.
            - gene_details: List of gene metadata for the selected subpanel.
            - germline_gene_symbols: List of germline gene symbols for the selected panel.
    """

    public_assay_map = app.config["PUBLIC_ASSAY_MAP"]
    public_assays = list(public_assay_map.keys())  # ["WGS", "ST-DNA", ...]

    selected_panel_name = request.args.get("panel")
    selected_subpanel_name = request.args.get("subpanel")

    subpanels = []
    gene_details = []
    germline_gene_symbols = []

    if selected_panel_name:
        assay_ids = public_assay_map.get(selected_panel_name, [])
        subpanels = store.isgl_handler.get_subpanels_for_asp(assay_ids)
        # TODO: Currently only one assay is selected, In future we should support multiple
        gene_symbols, germline_gene_symbols = store.asp_handler.get_asp_genes(
            assay_ids[0]
        )

        if selected_subpanel_name:
            gene_symbols = store.isgl_handler.get_asp_subpanel_genes(
                assay_ids[0], selected_subpanel_name
            )

        gene_details = store.hgnc_handler.get_metadata_by_symbols(gene_symbols)

    return render_template(
        "panel_gene_explorer.html",
        panels=public_assays,
        selected_panel_name=selected_panel_name,
        subpanels=subpanels,
        selected_subpanel_name=selected_subpanel_name,
        gene_details=gene_details,
        germline_gene_symbols=germline_gene_symbols,
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
    gene_symbols, germline_gene_symbols = store.asp_handler.get_asp_genes(
        asp_id
    )
    gene_details = store.hgnc_handler.get_metadata_by_symbols(gene_symbols)

    return render_template(
        "asp_genes.html",
        asp_id=asp_id,
        gene_details=gene_details,
        germline_gene_symbols=germline_gene_symbols,
    )
