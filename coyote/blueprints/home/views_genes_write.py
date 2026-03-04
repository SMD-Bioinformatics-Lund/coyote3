"""Home blueprint gene mutation routes."""

from __future__ import annotations

from flask import Response, jsonify, request
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.home import home_bp
from coyote.services.api_client.api_client import ApiRequestError
from coyote.services.api_client.home import (
    apply_isgl as apply_isgl_api,
)
from coyote.services.api_client.home import (
    clear_adhoc_genes as clear_adhoc_genes_api,
)
from coyote.services.api_client.home import (
    save_adhoc_genes as save_adhoc_genes_api,
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


@home_bp.route("/<string:sample_id>/apply_isgl", methods=["POST"])
@login_required
def apply_isgl(sample_id: str) -> tuple[Response, int] | Response:
    """Apply selected ISGL identifiers to a sample via API."""
    isgl_ids = request.get_json(silent=True)
    if not isinstance(isgl_ids, list):
        return jsonify({"status": "error", "error": "Invalid payload"}), 400

    try:
        payload = apply_isgl_api(sample_id, isgl_ids)
    except ApiRequestError as exc:
        return _mutation_error(
            exc,
            log_message=f"Failed to apply ISGL via API for sample {sample_id}",
        )

    return jsonify(payload)


@home_bp.route("/<string:sample_id>/adhoc_genes", methods=["POST"])
@login_required
def save_adhoc_genes(sample_id: str) -> tuple[Response, int] | Response:
    """Persist ad-hoc genes for a sample via API."""
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"status": "error", "error": "Invalid payload"}), 400

    try:
        payload = save_adhoc_genes_api(
            sample_id,
            genes=body.get("genes", ""),
            label=body.get("label", "adhoc"),
        )
    except ApiRequestError as exc:
        return _mutation_error(
            exc,
            log_message=f"Failed to save ad-hoc genes via API for sample {sample_id}",
        )

    return jsonify(payload)


@home_bp.route("/<string:sample_id>/adhoc_genes/clear", methods=["POST"])
@login_required
def clear_adhoc_genes(sample_id: str) -> tuple[Response, int] | Response:
    """Clear ad-hoc genes for a sample via API."""
    try:
        payload = clear_adhoc_genes_api(sample_id)
    except ApiRequestError as exc:
        return _mutation_error(
            exc,
            log_message=f"Failed to clear ad-hoc genes via API for sample {sample_id}",
        )

    return jsonify(payload)
