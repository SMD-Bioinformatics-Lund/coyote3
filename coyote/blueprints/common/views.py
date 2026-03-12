"""Common blueprint routes grouped by shared UI concern."""

from __future__ import annotations

import json
from typing import Any

from flask import Response, abort, current_app as app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from coyote.blueprints.common import common_bp
from coyote.blueprints.common.forms import TieredVariantSearchForm
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import log_api_error


@common_bp.route("/<string:sample_id>/<string:sample_assay>/genes", methods=["POST"])
def get_sample_genelists(sample_id: str, sample_assay: str) -> str:
    """Return sample genelists.

    Args:
        sample_id (str): Value for ``sample_id``.
        sample_assay (str): Value for ``sample_assay``.

    Returns:
        str: The function result.
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
    """Handle gene info.

    Args:
        id (str): Value for ``id``.

    Returns:
        str: The function result.
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


@common_bp.route("/reported_variants/variant/<string:variant_id>/<int:tier>", methods=["GET"])
@login_required
def list_samples_with_tiered_variant(variant_id: str, tier: int):
    """List samples with tiered variant.

    Args:
        variant_id (str): Value for ``variant_id``.
        tier (int): Value for ``tier``.

    Returns:
        The function result.
    """
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.common("reported_variants", "variant", variant_id, tier),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            abort(404)
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to fetch tiered variant context via API for {variant_id}",
            flash_message="Failed to load tiered variant context",
        )
        return render_template("tiered_variant_info.html", docs=[], variant={}, tier=tier)
    return render_template(
        "tiered_variant_info.html",
        docs=payload.get("docs", []),
        variant=payload.get("variant", {}),
        tier=payload.get("tier") or tier,
        error=payload.get("error"),
    )


@common_bp.route("/search/tiered_variants", methods=["GET", "POST"])
@login_required
def search_tiered_variants():
    """Handle search tiered variants.

    Returns:
        The function result.
    """
    form = TieredVariantSearchForm()
    search_mode = form.search_options.default
    include_annotation_text = form.include_annotation_text.default
    assays = form.assay.default

    search_str = None
    try:
        bootstrap_params = {
            "search_mode": search_mode,
            "include_annotation_text": str(bool(include_annotation_text)).lower(),
        }
        if assays:
            bootstrap_params["assays"] = assays
        bootstrap_payload = get_web_api_client().get_json(
            api_endpoints.common("search", "tiered_variants"),
            headers=forward_headers(),
            params=bootstrap_params,
        )
        form.assay.choices = bootstrap_payload.get("assay_choices", [])
    except ApiRequestError:
        form.assay.choices = []

    if request.method == "POST":
        if form.validate_on_submit():
            search_str = form.variant_search.data.strip()
            search_mode = form.search_options.data
            include_annotation_text = form.include_annotation_text.data
            assays = form.assay.data or None
        else:
            flash(form.variant_search.errors[0], "red")

    if request.method == "GET":
        qs = request.args
        if qs.get("search_str"):
            search_str = qs.get("search_str", "").strip()
            form.variant_search.data = search_str
        if qs.get("search_mode"):
            search_mode = qs.get("search_mode")
            form.search_options.data = search_mode
        if qs.get("include_annotation_text") is not None:
            include_annotation_text = qs.get("include_annotation_text") in (
                "1",
                "true",
                "True",
                "yes",
                "on",
            )
            form.include_annotation_text.data = include_annotation_text
        assays_qs = qs.getlist("assay")
        if assays_qs:
            assays = assays_qs
            form.assay.data = assays

    try:
        params = {"include_annotation_text": str(bool(include_annotation_text)).lower()}
        if search_str:
            params["search_str"] = search_str
        if search_mode:
            params["search_mode"] = search_mode
        if assays:
            params["assays"] = assays
        payload = get_web_api_client().get_json(
            api_endpoints.common("search", "tiered_variants"),
            headers=forward_headers(),
            params=params,
        )
        form.assay.choices = payload.get("assay_choices", [])
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message="Failed to search tiered variants via API",
            flash_message="Failed to search tiered variants",
        )
        form.assay.choices = []
        payload = None

    return render_template(
        "search_tiered_variants.html",
        docs=(payload.get("docs", []) if payload else []),
        search_str=(payload.get("search_str") if payload else search_str),
        search_mode=(payload.get("search_mode") if payload else search_mode),
        include_annotation_text=(
            payload.get("include_annotation_text") if payload else include_annotation_text
        ),
        tier_stats=(payload.get("tier_stats") if payload else {"total": {}, "by_assay": {}}),
        assays=(payload.get("assays") if payload else assays),
        form=form,
    )


def _redirect_for_omics_layer(sample_id: str, omics_layer: str) -> Response:
    """Handle  redirect for omics layer.

    Args:
            sample_id: Sample id.
            omics_layer: Omics layer.

    Returns:
            The  redirect for omics layer result.
    """
    if omics_layer == "dna":
        return redirect(url_for("dna_bp.list_small_variants", sample_id=sample_id))
    if omics_layer == "rna":
        return redirect(url_for("rna_bp.list_fusions", sample_id=sample_id))
    app.logger.info("Unrecognized omics type for sample %s! Unable to redirect to sample page", sample_id)
    flash("Unrecognized omics type! Unable to redirect to the sample page", "red")
    return redirect(url_for("home_bp.samples_home"))


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
@login_required
def add_sample_comment(sample_id: str) -> Response:
    """Handle add sample comment.

    Args:
        sample_id (str): Value for ``sample_id``.

    Returns:
        Response: The function result.
    """
    data = request.form.to_dict()
    try:
        get_web_api_client().post_json(
            api_endpoints.sample(sample_id, "comments"),
            headers=forward_headers(),
            json_body={"form_data": data},
        )
        flash("Sample comment added", "green")
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to add sample comment via API for sample {sample_id}",
            flash_message="Failed to add sample comment",
        )
    if request.endpoint == "common_bp.add_dna_sample_comment":
        return redirect(url_for("dna_bp.list_small_variants", sample_id=sample_id))
    return redirect(url_for("rna_bp.list_fusions", sample_id=sample_id))


@common_bp.route("/sample/<string:sample_id>/hide_sample_comment", methods=["POST"])
@login_required
def hide_sample_comment(sample_id: str) -> Response:
    """Handle hide sample comment.

    Args:
        sample_id (str): Value for ``sample_id``.

    Returns:
        Response: The function result.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        payload = get_web_api_client().patch_json(
            api_endpoints.sample(sample_id, "comments", comment_id, "hidden"),
            headers=forward_headers(),
        )
        omics_layer = str(payload.meta.get("omics_layer", "")).lower()
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to hide sample comment via API for sample {sample_id}",
            flash_message="Failed to hide sample comment",
        )
        return redirect(url_for("home_bp.samples_home"))
    return _redirect_for_omics_layer(sample_id, omics_layer)


@common_bp.route("/sample/unhide_sample_comment/<string:sample_id>", methods=["POST"])
@login_required
def unhide_sample_comment(sample_id: str) -> Response:
    """Handle unhide sample comment.

    Args:
        sample_id (str): Value for ``sample_id``.

    Returns:
        Response: The function result.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        payload = get_web_api_client().delete_json(
            api_endpoints.sample(sample_id, "comments", comment_id, "hidden"),
            headers=forward_headers(),
        )
        omics_layer = str(payload.meta.get("omics_layer", "")).lower()
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to unhide sample comment via API for sample {sample_id}",
            flash_message="Failed to unhide sample comment",
        )
        return redirect(url_for("home_bp.samples_home"))
    return _redirect_for_omics_layer(sample_id, omics_layer)
