"""Public blueprint assay catalog routes."""

from __future__ import annotations

import io

from flask import abort, current_app as app, render_template, send_file

from coyote.blueprints.public import public_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import ApiRequestError, get_web_api_client
from coyote.services.api_client.web import raise_page_load_error


@public_bp.route("/asp/genes/<asp_id>")
def asp_genes(asp_id: str) -> str:
    """
    Display genes for a specific public assay panel.
    """
    try:
        payload = get_web_api_client().get_json(api_endpoints.public("asp", asp_id, "genes"))
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load public assay genes for {asp_id}",
            summary="Unable to load assay genes.",
            not_found_summary="Assay panel not found.",
        )

    return render_template(
        "asp_genes.html",
        asp_id=payload.get("asp_id", asp_id),
        gene_details=payload.get("gene_details", []),
        germline_gene_symbols=payload.get("germline_gene_symbols", []),
    )


@public_bp.route("/assay-catalog-matrix")
def assay_catalog_matrix():
    """
    Gene × (modality → category → ISGL) matrix.
    """

    try:
        payload = get_web_api_client().get_json(
            api_endpoints.public("assay-catalog-matrix", "context")
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to load assay catalog matrix",
            summary="Unable to load the assay catalog matrix.",
        )
    return render_template("assay_catalog_matrix.html", **dict(payload))


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
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to load assay catalog",
            summary="Unable to load the assay catalog.",
        )
    return render_template("assay_catalog.html", **dict(payload))


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
    buf = io.BytesIO(str(payload.get("content", "")).encode("utf-8"))
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name=str(payload.get("filename", "genes.csv")),
    )


@public_bp.route("/assay-catalog/genes/<isgl_key>/view")
def assay_catalog_isgl_genes_view(isgl_key: str | None = None) -> str:
    """Handle assay catalog isgl genes view.

    Args:
        isgl_key (str | None): Value for ``isgl_key``.

    Returns:
        str: The function result.
    """
    if not isgl_key:
        return render_template("genes.html", gene_symbols=[])
    payload = get_web_api_client().get_json(
        api_endpoints.public("assay-catalog", "genes", isgl_key, "view_context")
    )

    return render_template(
        "genes.html",
        gene_symbols=payload.get("gene_symbols", []),
    )
