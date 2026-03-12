"""
Views for handling RNA fusion cases in the Coyote3 application.
All routes require user authentication and appropriate sample access.
"""

from __future__ import annotations

from copy import deepcopy

from flask import (
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.rna import rna_bp
from coyote.blueprints.rna.forms import FusionFilter
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import raise_page_load_error


@rna_bp.route("/sample/<string:sample_id>", methods=["GET", "POST"])
def list_fusions(sample_id: str) -> str | Response:
    """
    Display and filter RNA fusion events for a given sample.

    This view handles both GET and POST requests to display fusion events
    for the specified sample. It supports dynamic filtering of fusions
    based on user input, manages sample group and assay configuration,
    and prepares data for rendering the fusion list template.

    Parameters:
        sample_id (str): The sample identifier.

    Returns:
        Response: Rendered HTML template for the fusion list page.
    """
    headers = forward_headers()
    api_client = get_web_api_client()

    def _load_api_context():
        """Handle  load api context.

        Returns:
                The  load api context result.
        """
        payload = api_client.get_json(
            api_endpoints.rna_sample(sample_id, "fusions"),
            headers=headers,
        )
        return payload

    try:
        fusions_payload = _load_api_context()
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load RNA fusions for sample {sample_id}",
            summary="Unable to load RNA fusions for this sample.",
            not_found_summary="RNA fusion data for this sample was not found.",
        )

    sample = fusions_payload.sample
    assay_config = fusions_payload.assay_config
    sample_has_filters = sample.get("filters", None)
    assay_group = fusions_payload.assay_group or assay_config.get("asp_group", "unknown")
    subpanel = fusions_payload.subpanel
    fusionlist_options = fusions_payload.fusionlist_options
    sample_filters = deepcopy(fusions_payload.filters)
    filter_context = deepcopy(fusions_payload.filter_context)
    app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

    # Create the form
    form = FusionFilter()

    ###########################################################################
    ## FORM FILTERS ##
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        # Reset filters to defaults
        if form.reset.data:
            app.logger.info(f"Resetting filters to default settings for the sample {sample_id}")
            try:
                api_client.delete_json(
                    api_endpoints.sample(sample_id, "filters"),
                    headers=headers,
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to reset RNA filters via API for sample %s: %s", sample_id, exc
                )
        else:
            filters_from_form = {
                key: value
                for key, value in form.data.items()
                if key not in {"csrf_token", "reset", "submit"}
            }
            filters_from_form["fusionlist_id"] = request.form.getlist("fusionlist_id")
            try:
                api_client.put_json(
                    api_endpoints.sample(sample_id, "filters"),
                    headers=headers,
                    json_body={"filters": filters_from_form},
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to update RNA filters via API for sample %s: %s", sample_id, exc
                )

        try:
            fusions_payload = _load_api_context()
            sample = fusions_payload.sample
            assay_config = fusions_payload.assay_config
            sample_filters = deepcopy(fusions_payload.filters)
            filter_context = deepcopy(fusions_payload.filter_context)
            fusionlist_options = fusions_payload.fusionlist_options
        except ApiRequestError as exc:
            app.logger.error("RNA fusion API refresh failed for sample %s: %s", sample_id, exc)
            raise_page_load_error(
                exc,
                logger=app.logger,
                log_message=f"Failed to refresh RNA fusions for sample {sample_id}",
                summary="Unable to refresh RNA fusions for this sample.",
                not_found_summary="RNA fusion data for this sample was not found.",
            )

    if not sample_has_filters:
        try:
            api_client.delete_json(
                api_endpoints.sample(sample_id, "filters"),
                headers=headers,
            )
            fusions_payload = _load_api_context()
            sample = fusions_payload.sample
            assay_config = fusions_payload.assay_config
            sample_filters = deepcopy(fusions_payload.filters)
            filter_context = deepcopy(fusions_payload.filter_context)
            fusionlist_options = fusions_payload.fusionlist_options
        except ApiRequestError as exc:
            app.logger.error(
                "Failed to reset RNA filters via API for sample %s: %s", sample_id, exc
            )
    ############################################################################
    has_hidden_comments = fusions_payload.hidden_comments

    # Add them to the form and update with the requested settings
    form_data = deepcopy(sample_filters)
    form_data.update(
        {
            **{f"fusioncaller_{k}": True for k in filter_context["fusion_callers"]},
            **{f"fusioneffect_{k}": True for k in filter_context["fusion_effect_form_keys"]},
            **{f"fusionlist_{k}": True for k in filter_context["checked_fusionlists"]},
            **{assay_group: True},
        }
    )
    form.process(data=form_data)

    fusions = fusions_payload.fusions
    ai_text = fusions_payload.ai_text
    app.logger.info("Loaded RNA fusion list from API service for sample %s", sample_id)

    # Your logic for handling RNA samples
    return render_template(
        "list_fusions.html",
        sample=sample,
        form=form,
        fusions=fusions,
        fusionlist_options=fusionlist_options,
        checked_fusionlists=fusions_payload.checked_fusionlists,
        checked_fusionlists_dict=fusions_payload.checked_fusionlists_dict,
        hidden_comments=has_hidden_comments,
        ai_text=ai_text,
        sample_id=sample["_id"],
    )


@rna_bp.route("/<string:sample_id>/fusion/<string:fusion_id>")
def show_fusion(sample_id: str, fusion_id: str) -> Response | str:
    """
    Display details for a specific RNA fusion event.

    Retrieves the fusion by its ID, fetches the associated sample, obtains
    annotations and classification for the fusion, and renders the
    show_fusion.html template with this data.

    Args:
        sample_id (str): The unique identifier of the sample.
        fusion_id (str): The unique identifier of the fusion event.

    Returns:
        Response | str: Rendered HTML template for the fusion details page.
    """
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.rna_sample(sample_id, "fusions", fusion_id),
            headers=forward_headers(),
        )
        app.logger.info("Loaded RNA fusion detail from API service for sample %s", sample_id)
        return render_template(
            "show_fusion.html",
            fusion=payload.fusion,
            in_other=payload.in_other,
            sample=payload.sample,
            annotations=payload.annotations,
            latest_classification=payload.latest_classification,
            annotations_interesting=payload.annotations_interesting,
            other_classifications=payload.other_classifications,
            hidden_comments=payload.hidden_comments,
            assay_group=payload.assay_group,
            subpanel=payload.subpanel,
            assay_group_mappings=payload.assay_group_mappings,
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load RNA fusion detail for sample {sample_id} fusion {fusion_id}",
            summary="Unable to load the requested fusion.",
            not_found_summary="The requested fusion was not found for this sample.",
        )


def _bulk_fusion_flag_update(
    *,
    sample_id: str,
    apply: bool,
    fusion_ids: list[str],
    endpoint: str,
    log_message: str,
) -> None:
    """Apply a bulk fusion flag update through the canonical API."""
    try:
        get_web_api_client().patch_json(
            endpoint,
            headers=forward_headers(),
            params={"apply": str(apply).lower(), "fusion_ids": fusion_ids},
        )
    except ApiRequestError as exc:
        app.logger.error("%s for sample %s: %s", log_message, sample_id, exc)


@rna_bp.route("/<string:sample_id>/fusion/fp/<string:fus_id>", methods=["POST"])
def mark_false_fusion(sample_id: str, fus_id: str) -> Response:
    """Mark a fusion as false-positive and redirect back to its detail page."""
    try:
        get_web_api_client().patch_json(
            api_endpoints.rna_sample(sample_id, "fusions", fus_id, "flags", "false-positive"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to mark RNA fusion false-positive via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/unfp/<string:fus_id>", methods=["POST"])
def unmark_false_fusion(sample_id: str, fus_id: str) -> Response:
    """Remove the false-positive flag from a fusion and redirect back to its detail page."""
    try:
        get_web_api_client().delete_json(
            api_endpoints.rna_sample(sample_id, "fusions", fus_id, "flags", "false-positive"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to unmark RNA fusion false-positive via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route(
    "/<string:sample_id>/fusion/pickfusioncall/<string:fus_id>/<string:callidx>/<string:num_calls>",
    methods=["GET", "POST"],
)
def pick_fusioncall(sample_id: str, fus_id: str, callidx: str, num_calls: str) -> Response:
    """Select the active fusion call and redirect back to fusion detail."""
    try:
        get_web_api_client().patch_json(
            api_endpoints.rna_sample(sample_id, "fusions", fus_id, "selection", callidx, num_calls),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to pick RNA fusion call via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/hide_fusion_comment/<string:fus_id>", methods=["POST"])
def hide_fusion_comment(sample_id: str, fus_id: str) -> Response:
    """Hide a fusion comment and redirect back to fusion detail."""
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().patch_json(
            api_endpoints.rna_sample(
                sample_id, "fusions", fus_id, "comments", comment_id, "hidden"
            ),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to hide RNA fusion comment via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/unhide_fusion_comment/<string:fus_id>", methods=["POST"])
def unhide_fusion_comment(sample_id: str, fus_id: str) -> Response:
    """Unhide a fusion comment and redirect back to fusion detail."""
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().delete_json(
            api_endpoints.rna_sample(
                sample_id, "fusions", fus_id, "comments", comment_id, "hidden"
            ),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to unhide RNA fusion comment via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/multi_class/<sample_id>", methods=["POST"], endpoint="classify_multi_fusions")
@login_required
def classify_multi_fusions(sample_id: str) -> Response:
    """Apply supported bulk fusion actions from the list view."""
    action = request.form.get("action")
    fusion_ids = request.form.getlist("selected_object_id")
    tier = request.form.get("tier")
    irrelevant = request.form.get("irrelevant")
    false_positive = request.form.get("false_positive")

    if tier and action == "apply":
        flash(
            "Bulk tier assignment is not supported for RNA fusions. Use fusion detail page.",
            "yellow",
        )
    elif false_positive and action in {"apply", "remove"}:
        _bulk_fusion_flag_update(
            sample_id=sample_id,
            apply=action == "apply",
            fusion_ids=fusion_ids,
            endpoint=api_endpoints.rna_sample(sample_id, "fusions", "flags", "false-positive"),
            log_message="Failed to bulk update RNA false-positive fusion flags via API",
        )
    elif irrelevant and action in {"apply", "remove"}:
        _bulk_fusion_flag_update(
            sample_id=sample_id,
            apply=action == "apply",
            fusion_ids=fusion_ids,
            endpoint=api_endpoints.rna_sample(sample_id, "fusions", "flags", "irrelevant"),
            log_message="Failed to bulk update RNA irrelevant fusion flags via API",
        )
    return redirect(url_for("rna_bp.list_fusions", sample_id=sample_id))
