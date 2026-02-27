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

"""Public blueprint assay catalog routes."""

from __future__ import annotations

import io

from flask import abort, render_template, send_file

from coyote.blueprints.public import public_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, get_web_api_client


@public_bp.route("/asp/genes/<asp_id>")
def asp_genes(asp_id: str) -> str:
    """
    Display genes for a specific public assay panel.
    """
    payload = get_web_api_client().get_json(api_endpoints.public("asp", asp_id, "genes"))

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
    """

    payload = get_web_api_client().get_json(api_endpoints.public("assay-catalog-matrix", "context"))
    return render_template("assay_catalog_matrix.html", **payload.model_dump())


@public_bp.route("/assay-catalog")
@public_bp.route("/assay-catalog/<mod>")
@public_bp.route("/assay-catalog/<mod>/<cat>")
@public_bp.route("/assay-catalog/<mod>/<cat>/isgl/<isgl_key>")
def assay_catalog(mod: str | None = None, cat: str | None = None, isgl_key: str | None = None):
    """
    Display the assay catalog with modalities, categories, and gene lists.
    """
    try:
        params = {}
        if mod is not None:
            params["mod"] = mod
        if cat is not None:
            params["cat"] = cat
        if isgl_key is not None:
            params["isgl_key"] = isgl_key
        payload = get_web_api_client().get_json(
            api_endpoints.public("assay-catalog", "context"),
            params=params or None,
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            abort(404)
        raise
    return render_template("assay_catalog.html", **payload.model_dump())


@public_bp.route("/assay-catalog/<mod>/genes.csv")
@public_bp.route("/assay-catalog/<mod>/<cat>/genes.csv")
@public_bp.route("/assay-catalog/<mod>/<cat>/isgl/<isgl_key>/genes.csv")
def assay_catalog_genes_csv(mod: str, cat: str | None = None, isgl_key: str | None = None):
    """
    Export genes from the assay catalog as a CSV file.
    """
    params = {"mod": mod}
    if cat is not None:
        params["cat"] = cat
    if isgl_key is not None:
        params["isgl_key"] = isgl_key
    payload = get_web_api_client().get_json(
        api_endpoints.public("assay-catalog", "genes.csv", "context"),
        params=params,
    )
    buf = io.BytesIO(payload.content.encode("utf-8"))
    return send_file(buf, mimetype="text/csv", as_attachment=True, download_name=payload.filename)


@public_bp.route("/assay-catalog/genes/<isgl_key>/view")
def assay_catalog_isgl_genes_view(isgl_key: str | None = None) -> str:
    if not isgl_key:
        return render_template("genes.html", gene_symbols=[])
    payload = get_web_api_client().get_json(
        api_endpoints.public("assay-catalog", "genes", isgl_key, "view_context")
    )

    return render_template(
        "genes.html",
        gene_symbols=payload.gene_symbols,
    )
