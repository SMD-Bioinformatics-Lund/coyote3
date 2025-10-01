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
    send_file,
    abort,
)
import io
import zipfile
import csv
import datetime
import re

from werkzeug import Response
from coyote.extensions import store, util
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
@public_bp.route("/assay-catalog/<dna_rna>")  # DNA or RNA
@public_bp.route("/assay-catalog/<dna_rna>/<assay>")  # Assay family key (e.g., hematology)
@public_bp.route("/assay-catalog/<dna_rna>/<assay>/<dx>")  # Diagnosis key
def assay_catalog(dna_rna: str | None = None, assay: str | None = None, dx: str | None = None):
    """
    Public assays explorer (three-column layout)
    Column 1: assays (always)
    Column 2: diagnosis for selected assay with DNA/RNA toggle (always)
    Column 3: detail (landing → assay overview → dx overview + genes)
    """

    modality = util.public._norm_modality(dna_rna)  # 'dna' | 'rna' | None

    # Common: assays list for column 1 (always present)
    # Keep it unfiltered so the left column is stable.
    # assays_for_left = util.public._list_assays()
    assays_for_left = util.public._list_assays()
    # Landing page: /assays-explorer
    if not modality and not assay and not dx:
        return render_template(
            "assay_catalog.html",
            selected_dna_rna=None,
            assay_list=assays_for_left,  # Left column
            selected_assay=None,
            # Middle column has placeholder (no dx lists when no assay)
            diagnoses_dna=[],
            diagnoses_rna=[],
            # Right panel landing
            selected_dx=None,
            genes=[],
            germline_gene_symbols=[],
            assay_overview={"asp": {}, "dx": {}, "links": []},
            stats={"total_genes": 0, "diagnosis_count": 0},
        )

    # Modality page: /assays-explorer/<dna|rna>
    if modality and not assay and not dx:
        # Left column still shows all assays; middle column will show placeholder
        return render_template(
            "assay_catalog.html",
            selected_dna_rna=dna_rna.upper(),
            assay_list=assays_for_left,  # Left column
            selected_assay=None,
            diagnoses_dna=[],
            diagnoses_rna=[],
            selected_dx=None,
            genes=[],
            germline_gene_symbols=[],
            assay_overview={"asp": {}, "dx": {}, "links": []},
            stats={"total_genes": 0, "diagnosis_count": 0},
        )

    # Assay (family) page: /assays-explorer/<dna|rna>/<assay>
    if modality and assay and not dx:
        dna_cards = util.public._get_diagnosis_cards(assay, "dna")
        rna_cards = util.public._get_diagnosis_cards(assay, "rna")

        asp_ids = util.public._asp_ids_for_assay_modality(assay, modality)
        asp_genes, germline = util.public._union_asp_genes(asp_ids)
        gene_details = store.hgnc_handler.get_metadata_by_symbols(asp_genes)

        assay_overview = util.public._compose_assay_overview(assay, modality, None)

        return render_template(
            "assay_catalog.html",
            selected_dna_rna=dna_rna.upper(),
            assay_list=assays_for_left,  # Left column always filled
            selected_assay=assay,
            diagnoses_dna=dna_cards,  # Middle column
            diagnoses_rna=rna_cards,
            selected_dx=None,
            genes=gene_details,  # Right panel shows assay overview; gene table present or can be hidden
            germline_gene_symbols=sorted(germline),
            assay_overview=assay_overview,
            stats={
                "total_genes": len(asp_genes),
                "diagnosis_count": len(dna_cards) + len(rna_cards),
            },
        )

    # Diagnosis page: /assays-explorer/<dna|rna>/<assay>/<dx>
    if modality and assay and dx:
        bound_asp_ids = util.public._asp_ids_for_dx(assay, modality, dx)
        asp_union_genes, germline = util.public._union_asp_genes(bound_asp_ids)

        isgl_genes = store.isgl_handler.get_public_isgl_genes_by_diagnosis(dx)
        subset = sorted(set(asp_union_genes) & set(isgl_genes))
        gene_details = store.hgnc_handler.get_metadata_by_symbols(subset)

        assay_overview = util.public._compose_assay_overview(assay, modality, dx)

        # Middle column needs the full dx list for quick switching
        dna_cards = util.public._get_diagnosis_cards(assay, "dna")
        rna_cards = util.public._get_diagnosis_cards(assay, "rna")

        return render_template(
            "assay_catalog.html",
            selected_dna_rna=dna_rna.upper(),
            assay_list=assays_for_left,
            selected_assay=assay,
            diagnoses_dna=dna_cards,
            diagnoses_rna=rna_cards,
            selected_dx=dx,
            genes=gene_details,
            germline_gene_symbols=sorted(germline),
            assay_overview=assay_overview,
            stats={"total_genes": len(subset), "diagnosis_count": 1},
        )

    # Fallback → landing
    return render_template(
        "assay_catalog.html",
        selected_dna_rna=None,
        assay_list=assays_for_left,
        selected_assay=None,
        diagnoses_dna=[],
        diagnoses_rna=[],
        selected_dx=None,
        genes=[],
        germline_gene_symbols=[],
        assay_overview={"asp": {}, "dx": {}, "links": []},
        stats={"total_genes": 0, "diagnosis_count": 0},
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


@public_bp.route("/contact")
def contact() -> str:
    """
    Displays the contact information page.

    Returns:
        str: Rendered HTML page containing contact details.
    """
    contact = app.config.get("CONTACT") or {}
    return render_template("contact.html", contact=contact)


@public_bp.route("/assays/<modality>/<assay>/genes.csv", endpoint="download_asp_genes_csv")
@public_bp.route("/assays/<modality>/<assay>/<dx>/genes.csv", endpoint="download_asp_dx_genes_csv")
def download_genes_csv(
    modality: str | None = None, assay: str | None = None, dx: str | None = None
):
    """
    Generate CSV files for each ASP panel and return them as a ZIP archive.

    - If `dx` is not provided: includes all genes covered by each ASP panel for the selected modality.
    - If `dx` is provided: includes only genes present in both the ASP panel and the ISGL curation for the specified diagnosis.
    """
    # ---- guard / inputs ----
    mode = util.public._norm_modality(modality)  # 'dna' | 'rna' | None
    if mode not in ("dna", "rna"):
        abort(404)
    if not assay:
        flash("Assay family is required for gene list download.", "red")
        return redirect(request.referrer or "/")

    # Resolve ASP ids for (assay, modality)
    asp_ids = util.public._asp_ids_for_assay_modality(assay, mode) or []
    if not asp_ids:
        flash("No assay-specific panels found for this selection.", "yellow")
        return redirect(request.referrer or "/")

    # If dx given, fetch curated ISGL once
    isgl_genes = None
    if dx:
        isgl_genes = set(store.isgl_handler.get_public_isgl_genes_by_diagnosis(dx) or [])

    # ---- build ZIP in-memory ----
    today = datetime.date.today().isoformat()
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:

        for asp_id in asp_ids:
            # Get ASP coverage (symbols) + germline (unused in csv, but fetched anyway)
            asp_symbols, germline_symbols = store.asp_handler.get_asp_genes(asp_id)
            asp_symbols = set(asp_symbols or [])

            # TODO: We can also send asp and dx lists as a separate file if needed.
            # For now, just one CSV per ASP.
            # Filter by ISGL if dx given; sort for consistency
            if dx:
                symbols = sorted(asp_symbols & isgl_genes)
                fname = f"{assay}-{asp_id}.{dx}.{mode}.{today}.genes.csv"
            else:
                symbols = sorted(asp_symbols)
                fname = f"{assay}-{asp_id}.{mode}.{today}.genes.csv"

            # Hydrate gene metadata
            details = store.hgnc_handler.get_metadata_by_symbols(symbols) if symbols else []
            details = sorted(details, key=lambda g: (g.get("hgnc_symbol") or "").upper())

            # Write one CSV to a string buffer, then into the zip
            csv_io = io.StringIO()
            w = csv.writer(csv_io, lineterminator="\n")
            # Columns: keep clean + CSV-friendly
            w.writerow(
                [
                    "HGNC_ID",
                    "Gene_Symbol",
                    "Locus",
                    "Chromosome",
                    "Start",
                    "End",
                    "Aliases",
                    "Previous_Symbols",
                    "Gene_Type",
                    "Ensembl_Canonical",
                    "MANE_Select_RefSeq",
                    "MANE_Select_Ensembl",
                    "MANE_Plus_Clinical",
                    "OMIM",
                    "Description",
                ]
            )

            for g in details:
                aliases = "|".join((g.get("alias_symbol") or [])[:10])
                prev = "|".join((g.get("prev_symbol") or [])[:10])
                gtypes = ",".join(g.get("gene_type") or [])
                plus = "|".join(g.get("refseq_mane_plus_clinical") or [])
                # Handle either 'omim_id' (int list) or 'omim_ids' (string list)
                omims = g.get("omim_id") or g.get("omim_ids") or []
                omims = [str(x) for x in omims][:5]
                desc = (g.get("gene_description") or "").replace("\n", " ")
                w.writerow(
                    [
                        (g.get("hgnc_id") or "").replace("HGNC:", "HGNC:"),
                        g.get("hgnc_symbol") or "",
                        g.get("locus") or "",
                        g.get("chromosome") or "",
                        g.get("start") or "",
                        g.get("end") or "",
                        aliases,
                        prev,
                        gtypes,
                        "Yes" if g.get("ensembl_canonical") else "No",
                        g.get("refseq_mane_select") or "",
                        g.get("ensembl_mane_select") or "",
                        plus,
                        ",".join(omims),
                        desc,
                    ]
                )

            zf.writestr(fname, csv_io.getvalue().encode("utf-8"))

    zip_buf.seek(0)
    zip_name = f"{assay}.{mode}.{today}.genes.zip"
    if dx:
        zip_name = f"{assay}.{dx}.{mode}.{today}.genes.zip"

    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name,
        max_age=0,
        etag=False,
    )
