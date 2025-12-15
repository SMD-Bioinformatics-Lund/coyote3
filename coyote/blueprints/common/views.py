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
This module defines Flask view functions for handling error screens and sample comment operations within the Coyote3 project. It includes routes for displaying errors, adding, hiding, and unhiding sample comments, and retrieving gene lists for samples. Access control and user authentication are enforced via decorators.
"""

from flask import Response, redirect, request, url_for, flash
from flask import current_app as app
from coyote.blueprints.common import common_bp
from coyote.extensions import store, util
from flask import render_template
from flask_login import current_user
import traceback
from coyote.util.decorators.access import require_sample_access
from coyote.services.auth.decorators import require
import json


@common_bp.route(
    "/dna/sample/<string:sample_id>/sample_comment",
    methods=["POST"],
    endpoint="add_dna_sample_comment",
)
@common_bp.route(
    "/rna/sample/<string:sample_id>/sample_comment",
    methods=["POST"],
    endpoint="add_rna_sample_comment",
)
@common_bp.route("/sample/<string:sample_id>/sample_comment", methods=["POST"])
@require_sample_access("sample_id")
@require("add_sample_comment", min_role="user", min_level=9)
def add_sample_comment(sample_id: str) -> Response:
    """
    Add Sample comment
    """
    data = request.form.to_dict()
    doc = util.bpcommon.create_comment_doc(data, key="sample_comment")
    store.sample_handler.add_sample_comment(sample_id, doc)
    flash("Sample comment added", "green")
    if request.endpoint == "common_bp.add_dna_sample_comment":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    else:
        return redirect(url_for("rna_bp.list_fusions", id=sample_id))


@common_bp.route("/sample/<string:sample_id>/hide_sample_comment", methods=["POST"])
@require_sample_access("sample_id")
@require("hide_sample_comment", min_role="manager", min_level=99)
def hide_sample_comment(sample_id: str) -> Response:
    """
    Hides a sample comment for the given sample.

    Args:
        sample_id (str): The identifier of the sample.

    Returns:
        Response: Redirects to the appropriate variant or fusion list page based on sample type.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.sample_handler.hide_sample_comment(sample_id, comment_id)
    sample = store.sample_handler.get_sample_by_id(sample_id)

    if sample.get("omics_layer", "").lower() == "dna":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    elif sample.get("omics_layer", "").lower() == "rna":
        return redirect(url_for("rna_bp.list_fusions", id=sample_id))
    else:
        app.logger.info(
            f"Unrecognized omics type {sample["name"]}! Unable to redirect to the sample page"
        )
        flash("Unrecognized omics type! Unable to redirect to the sample page", "red")
        return redirect(url_for("home_bp.samples_home"))


@common_bp.route("/sample/unhide_sample_comment/<string:sample_id>", methods=["POST"])
@require_sample_access("sample_id")
@require("unhide_sample_comment", min_role="manager", min_level=99)
def unhide_sample_comment(sample_id: str) -> Response:
    """
    Unhides a previously hidden sample comment for the given sample.

    Args:
        sample_id (str): The identifier of the sample.

    Returns:
        Response: Redirects to the appropriate variant or fusion list page based on sample type.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.sample_handler.unhide_sample_comment(sample_id, comment_id)
    sample = store.sample_handler.get_sample_by_id(sample_id)
    if sample.get("omics_layer", "").lower() == "dna":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    elif sample.get("omics_layer", "").lower() == "rna":
        return redirect(url_for("rna_bp.list_fusions", id=sample_id))
    else:
        app.logger.info(
            f"Unrecognized omics type {sample["name"]}! Unable to redirect to the sample page"
        )
        flash("Unrecognized omics type! Unable to redirect to the sample page", "red")
        return redirect(url_for("home_bp.samples_home"))


@common_bp.route("/<string:sample_id>/<string:sample_assay>/genes", methods=["POST"])
def get_sample_genelists(sample_id: str, sample_assay: str) -> str:
    """
    Retrieves and decrypts gene list and panel document data from the request form, then renders the 'sample_genes.html' template with the provided sample information.

    Args:
        sample_id (Any): The identifier for the sample.
        sample_assay (Any): The assay type or identifier for the sample.

    Returns:
        str: Rendered HTML content for the 'sample_genes.html' template.

    Raises:
        KeyError: If required form fields ('enc_genelists' or 'enc_panel_doc') are missing.
        Exception: If decryption or JSON decoding fails.
    """
    enc_genelists = request.form.get("enc_genelists")
    enc_panel_doc = request.form.get("enc_panel_doc")
    enc_sample_filters = request.form.get("enc_sample_filters")

    fernet_obj = app.config.get("FERNET")

    genelists = json.loads(fernet_obj.decrypt(enc_genelists.encode()))
    panel_doc = json.loads(fernet_obj.decrypt(enc_panel_doc.encode()))

    sample_filters = json.loads(fernet_obj.decrypt(enc_sample_filters.encode()))
    adhoc_genes = sample_filters.pop("adhoc_genes", "")
    if adhoc_genes:
        filter_gl = sample_filters.get("genelists", [])
        filter_gl.append(adhoc_genes.get("label", "Adhoc"))
        sample_filters["genelists"] = filter_gl

    return render_template(
        "sample_genes.html",
        sample=sample_id,
        genelists=genelists,
        asp_config=panel_doc,
        sample_filters=sample_filters,
    )


@common_bp.route("/public/gene/<string:id>/info", endpoint="public_gene_info", methods=["GET"])
@common_bp.route("/gene/<string:id>/info", endpoint="gene_info", methods=["GET"])
def gene_info(id: str) -> str:
    """
    Fetches and displays detailed information about a gene based on its HGNC ID.

    Args:
        hgnc_id (str): The HGNC ID of the gene to retrieve information for.
    Returns:
        str: Rendered HTML content for the 'gene_info.html' template.
    """

    if id.isnumeric():
        gene = store.hgnc_handler.get_metadata_by_hgnc_id(hgnc_id=id)
    else:
        gene = store.hgnc_handler.get_metadata_by_symbol(symbol=id)

    return render_template("gene_info.html", gene=gene)
