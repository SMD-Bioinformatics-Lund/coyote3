"""Home blueprint sample list/edit routes."""

from __future__ import annotations

from flask import Response, redirect, render_template, request, url_for
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.home import home_bp
from coyote.blueprints.home.forms import SampleSearchForm
from coyote.services.api_client.api_client import ApiRequestError
from coyote.services.api_client.home import fetch_edit_context, fetch_samples
from coyote.services.api_client.web import log_api_error


def _resolve_search_mode(
    *,
    status: str,
    slider_value: str | None,
    submitted_mode: str | None,
) -> str:
    if submitted_mode in {"done", "both", "live"}:
        return submitted_mode
    slider_to_mode = {"1": "done", "2": "both", "3": "live"}
    if slider_value in slider_to_mode:
        return slider_to_mode[slider_value]
    if status in {"done", "live"}:
        return status
    return "live"


@home_bp.route("/samples", defaults={"status": "live"}, methods=["GET", "POST"])
@home_bp.route("/samples/<string:status>", methods=["GET", "POST"])
@login_required
def samples_home(status: str) -> str:
    """Render the sample dashboard using API-provided context."""
    form = SampleSearchForm()

    panel_type = request.args.get("panel_type") or None
    panel_tech = request.args.get("panel_tech") or None
    assay_group = request.args.get("assay_group") or None

    sample_search = (request.values.get("sample_search") or "").strip()
    search_mode = _resolve_search_mode(
        status=status,
        slider_value=request.values.get("search_mode_slider"),
        submitted_mode=request.values.get("search_mode"),
    )

    if request.method == "POST":
        form.sample_search.data = sample_search
        slider_value = request.values.get("search_mode_slider")
        if slider_value and slider_value.isdigit():
            form.search_mode_slider.data = int(slider_value)

    try:
        payload = fetch_samples(
            status=status,
            search_str=sample_search,
            search_mode=search_mode,
            panel_type=panel_type,
            panel_tech=panel_tech,
            assay_group=assay_group,
        )
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message="Failed to fetch home sample context via API",
            flash_message="Failed to load samples.",
        )
        payload = {
            "live_samples": [],
            "done_samples": [],
            "status": status,
            "search_mode": search_mode,
            "panel_type": panel_type,
            "panel_tech": panel_tech,
            "assay_group": assay_group,
        }

    return render_template(
        "samples_home.html",
        form=form,
        live_samples=payload.get("live_samples", []),
        done_samples=payload.get("done_samples", []),
        status=payload.get("status", status),
        search_mode=payload.get("search_mode", search_mode),
        panel_type=payload.get("panel_type", panel_type),
        panel_tech=payload.get("panel_tech", panel_tech),
        assay_group=payload.get("assay_group", assay_group),
        search_str=sample_search,
    )


@home_bp.route("/samples/edit/<string:sample_id>", methods=["GET"])
@login_required
def edit_sample(sample_id: str) -> str | Response:
    """Render sample edit view from API-provided context."""
    try:
        payload = fetch_edit_context(sample_id)
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message=f"Failed to fetch edit context via API for sample {sample_id}",
            flash_message="Failed to load sample settings.",
        )
        return redirect(url_for("home_bp.samples_home"))

    return render_template(
        "edit_sample.html",
        sample=payload.get("sample", {}),
        asp=payload.get("asp", {}),
        variant_stats_raw=payload.get("variant_stats_raw"),
        variant_stats_filtered=payload.get("variant_stats_filtered"),
    )
