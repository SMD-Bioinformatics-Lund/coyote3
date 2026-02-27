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

"""Common blueprint gene and sample gene-list routes."""

import json
from typing import Any

from flask import current_app as app
from flask import render_template, request

from coyote.blueprints.common import common_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.integrations.api.web import log_api_error


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
    _ = sample_assay
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
    gene: dict[str, Any] = {}
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.common("gene", id, "info"),
            headers=forward_headers(),
        )
        gene = payload.gene or {}
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to fetch gene info via API for {id}",
            flash_message="Failed to load gene info",
        )
    return render_template("gene_info.html", gene=gene)
