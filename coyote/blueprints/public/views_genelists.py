"""Public blueprint genelist routes."""

from __future__ import annotations

from flask import current_app as app
from flask import render_template, request
from werkzeug import Response

from coyote.blueprints.public import public_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import ApiRequestError, get_web_api_client
from coyote.services.api_client.web import raise_page_load_error


@public_bp.route("/genelists/<genelist_id>/view", methods=["GET"])
def view_genelist(genelist_id: str) -> Response | str:
    """
    Display a specific genelist and optionally filter its genes by a selected assay.
    """
    selected_assay = request.args.get("assay")
    try:
        params = {"assay": selected_assay} if selected_assay else None
        payload = get_web_api_client().get_json(
            api_endpoints.public("genelists", genelist_id, "view_context"),
            params=params,
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load public genelist {genelist_id}",
            summary="Unable to load the genelist.",
            not_found_summary="Genelist not found.",
        )

    return render_template(
        "isgl/view_isgl.html",
        genelist=payload.genelist,
        selected_assay=payload.selected_assay,
        filtered_genes=payload.filtered_genes,
        germline_genes=payload.germline_genes,
        is_public=payload.is_public,
    )
