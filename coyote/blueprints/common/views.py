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
This module defines Flask view functions for handling error screens and sample comment
operations within the Coyote3 project. It includes routes for displaying errors, adding,
hiding, and unhiding sample comments, and retrieving gene lists for samples. Access control
and user authentication are enforced via decorators.
"""

from flask import Response, redirect, request, url_for, flash, abort
from flask import current_app as app
from coyote.blueprints.common import common_bp
from coyote.blueprints.common.forms import TieredVariantSearchForm
from flask import render_template
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
import json
from flask_login import login_required
from typing import Any


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
    """
    Add Sample comment
    """
    data = request.form.to_dict()
    try:
        get_web_api_client().post_json(
            api_endpoints.sample(sample_id, "sample_comments", "add"),
            headers=forward_headers(),
            json_body={"form_data": data},
        )
        flash("Sample comment added", "green")
    except ApiRequestError as exc:
        app.logger.error("Failed to add sample comment via API for sample %s: %s", sample_id, exc)
        flash("Failed to add sample comment", "red")
    if request.endpoint == "common_bp.add_dna_sample_comment":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    else:
        return redirect(url_for("rna_bp.list_fusions", sample_id=sample_id))


@common_bp.route("/sample/<string:sample_id>/hide_sample_comment", methods=["POST"])
@login_required
def hide_sample_comment(sample_id: str) -> Response:
    """
    Hides a sample comment for the given sample.

    Args:
        sample_id (str): The identifier of the sample.

    Returns:
        Response: Redirects to the appropriate variant or fusion list page based on sample type.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.sample(sample_id, "sample_comments", comment_id, "hide"),
            headers=forward_headers(),
        )
        omics_layer = str(payload.meta.get("omics_layer", "")).lower()
    except ApiRequestError as exc:
        app.logger.error("Failed to hide sample comment via API for sample %s: %s", sample_id, exc)
        flash("Failed to hide sample comment", "red")
        return redirect(url_for("home_bp.samples_home"))

    if omics_layer == "dna":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    elif omics_layer == "rna":
        return redirect(url_for("rna_bp.list_fusions", sample_id=sample_id))
    else:
        app.logger.info("Unrecognized omics type for sample %s! Unable to redirect to sample page", sample_id)
        flash("Unrecognized omics type! Unable to redirect to the sample page", "red")
        return redirect(url_for("home_bp.samples_home"))


@common_bp.route("/sample/unhide_sample_comment/<string:sample_id>", methods=["POST"])
@login_required
def unhide_sample_comment(sample_id: str) -> Response:
    """
    Unhides a previously hidden sample comment for the given sample.

    Args:
        sample_id (str): The identifier of the sample.

    Returns:
        Response: Redirects to the appropriate variant or fusion list page based on sample type.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.sample(sample_id, "sample_comments", comment_id, "unhide"),
            headers=forward_headers(),
        )
        omics_layer = str(payload.meta.get("omics_layer", "")).lower()
    except ApiRequestError as exc:
        app.logger.error("Failed to unhide sample comment via API for sample %s: %s", sample_id, exc)
        flash("Failed to unhide sample comment", "red")
        return redirect(url_for("home_bp.samples_home"))

    if omics_layer == "dna":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    elif omics_layer == "rna":
        return redirect(url_for("rna_bp.list_fusions", sample_id=sample_id))
    else:
        app.logger.info("Unrecognized omics type for sample %s! Unable to redirect to sample page", sample_id)
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
    gene: dict[str, Any] = {}
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.common("gene", id, "info"),
            headers=forward_headers(),
        )
        gene = payload.gene or {}
    except ApiRequestError as exc:
        app.logger.error("Failed to fetch gene info via API for %s: %s", id, exc)
        flash("Failed to load gene info", "red")
    return render_template("gene_info.html", gene=gene)


@common_bp.route("/reported_variants/variant/<string:variant_id>/<int:tier>", methods=["GET"])
@login_required
def list_samples_with_tiered_variant(variant_id: str, tier: int):
    """
    Show reported variants across samples that match this variant identity and tier.
    """
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.common("reported_variants", "variant", variant_id, tier),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            abort(404)
        app.logger.error("Failed to fetch tiered variant context via API for %s: %s", variant_id, exc)
        flash("Failed to load tiered variant context", "red")
        return render_template("tiered_variant_info.html", docs=[], variant={}, tier=tier)
    return render_template(
        "tiered_variant_info.html",
        docs=payload.docs,
        variant=payload.variant,
        tier=payload.tier or tier,
        error=payload.error,
    )


@common_bp.route("/search/tiered_variants", methods=["GET", "POST"])
@login_required
def search_tiered_variants():
    """
    Search reported variants across samples by gene name, variant id, HGVSc, or HGVSp.
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
        form.assay.choices = bootstrap_payload.assay_choices
    except ApiRequestError:
        form.assay.choices = []

    if request.method == "POST":
        if form.validate_on_submit():
            search_str = form.variant_search.data.strip()
            search_mode = form.search_options.data
            include_annotation_text: bool = form.include_annotation_text.data
            assays: list[Any] | None = form.assay.data or None
        else:
            flash(form.variant_search.errors[0], "red")

    # Allow GET deep-links (from variant pages etc.)
    if request.method == "GET":
        qs = request.args

        # search string
        if qs.get("search_str"):
            search_str = qs.get("search_str", "").strip()
            form.variant_search.data = search_str

        # mode (gene / variant / transcript / etc)
        if qs.get("search_mode"):
            search_mode = qs.get("search_mode")
            form.search_options.data = search_mode

        # checkbox
        if qs.get("include_annotation_text") is not None:
            include_annotation_text = qs.get("include_annotation_text") in (
                "1",
                "true",
                "True",
                "yes",
                "on",
            )
            form.include_annotation_text.data = include_annotation_text

        # assays (multi)
        assays_qs = qs.getlist("assay")
        if assays_qs:
            assays = assays_qs
            form.assay.data = assays

    try:
        params = {
            "include_annotation_text": str(bool(include_annotation_text)).lower(),
        }
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
        form.assay.choices = payload.assay_choices
    except ApiRequestError as exc:
        app.logger.error("Failed to search tiered variants via API: %s", exc)
        flash("Failed to search tiered variants", "red")
        form.assay.choices = []
        payload = None

    return render_template(
        "search_tiered_variants.html",
        docs=(payload.docs if payload else []),
        search_str=(payload.search_str if payload else search_str),
        search_mode=(payload.search_mode if payload else search_mode),
        include_annotation_text=(
            payload.include_annotation_text if payload else include_annotation_text
        ),
        tier_stats=(payload.tier_stats if payload else {"total": {}, "by_assay": {}}),
        assays=(payload.assays if payload else assays),
        form=form,
    )
