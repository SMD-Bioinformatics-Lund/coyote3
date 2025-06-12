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
Coyote Public Facing Routes
"""


from flask import current_app as app
from flask import (
    redirect,
    render_template,
    request,
    url_for,
    send_from_directory,
    flash,
    abort,
    send_file,
)
from flask_login import current_user, login_required
from pprint import pformat
from copy import deepcopy

from werkzeug import Response
from coyote.extensions import store, util
from coyote.blueprints.public import public_bp
from coyote.util.decorators.access import require_sample_access
from coyote.services.auth.decorators import require


@public_bp.route("/genelists/<genelist_id>/view", methods=["GET"])
def view_genelist(genelist_id) -> Response | str:
    """
    Display a specific genelist and optionally filter its genes by a selected assay.

    Retrieves the genelist identified by `genelist_id` from the data store. If the genelist does not exist,
    flashes an error message and redirects to the current page.

    If an assay is selected via the "assay" query parameter and it exists in the genelist's assays,
    filters the genes to include only those covered by the selected panel, unless the panel technology is "WGS",
    in which case all genes are shown.

    Renders the "genelists/view_genelist.html" template with the genelist, selected assay, filtered genes,
    and a flag indicating the view is public.

    Args:
        genelist_id (str): The unique identifier for the genelist to view.

    Returns:
        flask.Response: The rendered template or a redirect response if the genelist is not found.
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
            if panel.get("panel_technology") != "WGS"
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
    Renders a matrix view of all in-silico genelists and their associated assays, grouped by public assay labels.

    Retrieves all in-silico genelists from the data store and groups their associated assays using the public assay mapping
    defined in the application configuration. Passes this data to the 'genepanel_matrix.html' template for rendering.

    Returns:
        str: Rendered HTML page displaying the genelist-assay matrix.
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
    Renders the gene explorer panel for public assays.
    This view function handles the selection of a panel and subpanel, retrieves the corresponding subpanels and gene details, and renders the 'panel_gene_explorer.html' template with the relevant data.
    Query Parameters:
        panel (str, optional): The name of the selected panel.
        subpanel (str, optional): The name of the selected subpanel.
    Returns:
        flask.Response: Rendered HTML template with the following context variables:
            - panels: List of available public assay panel names.
            - selected_panel_name: Name of the currently selected panel.
            - subpanels: List of subpanels for the selected panel.
            - selected_subpanel_name: Name of the currently selected subpanel.
            - gene_details: List of gene details for the selected subpanel.
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
