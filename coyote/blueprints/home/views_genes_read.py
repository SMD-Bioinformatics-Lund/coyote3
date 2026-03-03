
"""Home blueprint gene read routes."""

from flask import Response, jsonify
from flask import current_app as app

from coyote.blueprints.home import home_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.api_client.web import log_api_error


@home_bp.route("/<string:sample_id>/isgls", methods=["GET"])
def list_isgls(sample_id: str) -> Response:
    """
    Return adhoc in-study gene lists for the sample's assay as JSON.
    """
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.home_sample(sample_id, "isgls"),
            headers=forward_headers(),
        )
        return jsonify({"items": payload.items})
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message=f"Failed to fetch ISGLs via API for sample {sample_id}",
        )
        return jsonify({"items": []})


@home_bp.route("/<string:sample_id>/effective-genes/all", methods=["GET"])
def get_effective_genes_all(sample_id: str) -> Response:
    """
    Return all effective genes for the sample as JSON.
    """
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.home_sample(sample_id, "effective_genes", "all"),
            headers=forward_headers(),
        )
        return jsonify(
            {
                "items": payload.items,
                "asp_covered_genes_count": payload.asp_covered_genes_count,
            }
        )
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message=f"Failed to fetch effective genes via API for sample {sample_id}",
        )
        return jsonify({"items": [], "asp_covered_genes_count": 0})
