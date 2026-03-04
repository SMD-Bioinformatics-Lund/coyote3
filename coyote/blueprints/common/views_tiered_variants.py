"""Common blueprint tiered variant search/report routes."""

from flask import abort, flash, render_template, request
from flask import current_app as app
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
