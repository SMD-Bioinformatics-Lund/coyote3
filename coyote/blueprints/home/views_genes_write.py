"""Home blueprint gene mutation routes."""

from __future__ import annotations

from flask import Response, jsonify, request
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.home import home_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import log_api_error


def _mutation_error(exc: ApiRequestError, *, log_message: str) -> tuple[Response, int]:
    status = exc.status_code or 500
    payload = exc.payload if isinstance(exc.payload, dict) else None
    message = payload.get("error") if payload else str(exc)
    log_api_error(
        exc,
        logger=app.home_logger,
        log_message=log_message,
    )
    return jsonify({"status": "error", "error": message}), status


@home_bp.route("/samples/<string:sample_id>/apply_isgl", methods=["POST"])
@login_required
def apply_isgl(sample_id: str) -> tuple[Response, int] | Response:
    """Apply selected ISGL identifiers to a sample via API."""
    isgl_ids = request.get_json(silent=True)
    if not isinstance(isgl_ids, list):
        return jsonify({"status": "error", "error": "Invalid payload"}), 400

    try:
        payload = get_web_api_client().post_json(
            api_endpoints.home_sample(sample_id, "genes", "apply-isgl"),
            headers=forward_headers(),
            json_body={"isgl_ids": isgl_ids},
        )
    except ApiRequestError as exc:
        return _mutation_error(
            exc,
            log_message=f"Failed to apply ISGL via API for sample {sample_id}",
        )

    return jsonify(payload)


@home_bp.route("/samples/<string:sample_id>/adhoc_genes", methods=["POST"])
@login_required
def save_adhoc_genes(sample_id: str) -> tuple[Response, int] | Response:
    """Persist ad-hoc genes for a sample via API."""
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"status": "error", "error": "Invalid payload"}), 400

    try:
        payload = get_web_api_client().post_json(
            api_endpoints.home_sample(sample_id, "adhoc_genes", "save"),
            headers=forward_headers(),
            json_body={
                "genes": body.get("genes", ""),
                "label": body.get("label", "adhoc"),
            },
        )
    except ApiRequestError as exc:
        return _mutation_error(
            exc,
            log_message=f"Failed to save ad-hoc genes via API for sample {sample_id}",
        )

    return jsonify(payload)


@home_bp.route("/samples/<string:sample_id>/adhoc_genes/clear", methods=["POST"])
@login_required
def clear_adhoc_genes(sample_id: str) -> tuple[Response, int] | Response:
    """Clear ad-hoc genes for a sample via API."""
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.home_sample(sample_id, "adhoc_genes", "clear"),
            headers=forward_headers(),
            json_body={},
        )
    except ApiRequestError as exc:
        return _mutation_error(
            exc,
            log_message=f"Failed to clear ad-hoc genes via API for sample {sample_id}",
        )

    return jsonify(payload)
