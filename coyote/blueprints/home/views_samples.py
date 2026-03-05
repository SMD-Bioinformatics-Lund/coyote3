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


def _resolve_sample_view(*, status: str, submitted_view: str | None) -> str:
    view = (submitted_view or "").strip().lower()
    if view in {"live", "reported", "all"}:
        return view
    status_norm = (status or "").strip().lower()
    if status_norm in {"done", "reported"}:
        return "reported"
    return "live"


def _sample_view_to_search_mode(sample_view: str) -> str:
    return {"reported": "done", "all": "both", "live": "live"}.get(sample_view, "live")


def _sample_view_to_status(sample_view: str) -> str:
    return "done" if sample_view == "reported" else "live"


def _resolve_per_page(
    *,
    query_key: str,
    legacy_query_key: str,
    user_settings_key: str,
    default_value: int,
    user_settings: dict | None = None,
) -> int:
    """
    Resolve per-page value with precedence:
    query param -> user settings -> hardcoded default.
    This is intentionally generic for future user-configurable preferences.
    """
    query_value = request.args.get(query_key, type=int)
    if not query_value:
        query_value = request.args.get(legacy_query_key, type=int)
    if query_value:
        return max(1, min(query_value, 200))
    if user_settings:
        settings_value = user_settings.get(user_settings_key)
        if isinstance(settings_value, int):
            return max(1, min(settings_value, 200))
    return max(1, min(default_value, 200))


def _resolve_page_param(short_key: str, legacy_key: str, default: int = 1) -> int:
    return max(
        1,
        request.args.get(short_key, default=request.args.get(legacy_key, default=default, type=int), type=int)
        or default,
    )


@home_bp.route("", defaults={"status": "live"}, methods=["GET"])
@home_bp.route("/<string:status>", methods=["GET"])
@login_required
def samples_home(status: str) -> str:
    """Render the sample dashboard using API-provided context."""
    form = SampleSearchForm()

    panel_type = request.args.get("panel_type") or None
    panel_tech = request.args.get("panel_tech") or None
    assay_group = request.args.get("assay_group") or None

    sample_search = (request.args.get("q") or request.args.get("sample_search") or "").strip()
    sample_view = _resolve_sample_view(
        status=status,
        submitted_view=request.args.get("view"),
    )
    page = max(1, request.args.get("page", default=1, type=int) or 1)  # legacy global page
    per_page = max(1, min(request.args.get("per_page", default=30, type=int) or 30, 200))  # legacy fallback
    # Placeholder for future persisted user preferences.
    # When user settings are implemented, populate this from current user profile.
    user_settings: dict | None = None
    live_page = _resolve_page_param("lp", "live_page", default=1)
    done_page = _resolve_page_param("dp", "done_page", default=1)
    live_per_page = _resolve_per_page(
        query_key="lpp",
        legacy_query_key="live_per_page",
        user_settings_key="home_live_per_page",
        default_value=30,
        user_settings=user_settings,
    )
    done_per_page = _resolve_per_page(
        query_key="dpp",
        legacy_query_key="done_per_page",
        user_settings_key="home_done_per_page",
        default_value=30,
        user_settings=user_settings,
    )
    profile_scope = (request.args.get("scope") or request.args.get("profile_scope") or "production").strip().lower()
    if profile_scope not in {"production", "all"}:
        profile_scope = "production"
    search_mode = _sample_view_to_search_mode(sample_view)
    status_for_api = _sample_view_to_status(sample_view)

    # GET-only flow (PRG-like behavior): search updates URL directly.
    form.sample_search.data = sample_search

    try:
        payload = fetch_samples(
            status=status_for_api,
            search_str=sample_search,
            search_mode=search_mode,
            sample_view=sample_view,
            page=page,
            per_page=per_page,
            live_page=live_page,
            done_page=done_page,
            live_per_page=live_per_page,
            done_per_page=done_per_page,
            profile_scope=profile_scope,
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
            "sample_view": sample_view,
            "page": page,
            "per_page": per_page,
            "live_page": live_page,
            "done_page": done_page,
            "live_per_page": live_per_page,
            "done_per_page": done_per_page,
            "profile_scope": profile_scope,
            "has_next_live": False,
            "has_next_done": False,
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
        sample_view=payload.get("sample_view", sample_view),
        page=payload.get("page", page),
        per_page=payload.get("per_page", per_page),
        live_page=payload.get("live_page", live_page),
        done_page=payload.get("done_page", done_page),
        live_per_page=payload.get("live_per_page", live_per_page),
        done_per_page=payload.get("done_per_page", done_per_page),
        profile_scope=payload.get("profile_scope", profile_scope),
        has_next_live=payload.get("has_next_live", False),
        has_next_done=payload.get("has_next_done", False),
        panel_type=payload.get("panel_type", panel_type),
        panel_tech=payload.get("panel_tech", panel_tech),
        assay_group=payload.get("assay_group", assay_group),
        search_str=sample_search,
    )


@home_bp.route("/edit/<string:sample_id>", methods=["GET"])
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
