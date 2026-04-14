"""Home blueprint gene-related routes."""

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
    """Mutation error.

    Args:
            exc: Exc.
            log_message: Log message. Keyword-only argument.

    Returns:
            The  mutation error result.
    """
    status = exc.status_code or 500
    payload = exc.payload if isinstance(exc.payload, dict) else None
    message = payload.get("error") if payload else str(exc)
    log_api_error(
        exc,
        logger=app.home_logger,
        log_message=log_message,
    )
    return jsonify({"status": "error", "error": message}), status


@home_bp.route("/<string:sample_id>/isgls", methods=["GET"])
def list_isgls(sample_id: str) -> Response:
    """List isgls.

    Args:
        sample_id (str): Normalized ``sample_id``.

    Returns:
        Response: Normalized return value.
    """
    try:
        list_type = str(request.args.get("target") or "").strip().lower() or None
        payload = get_web_api_client().get_json(
            api_endpoints.home_sample(sample_id, "isgls"),
            headers=forward_headers(),
            params={"target": list_type} if list_type else None,
        )
        return jsonify({"items": payload.get("items", [])})
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message=f"Failed to fetch ISGLs via API for sample {sample_id}",
        )
        return jsonify({"items": []})


@home_bp.route("/<string:sample_id>/effective-genes/all", methods=["GET"])
def get_effective_genes_all(sample_id: str) -> Response:
    """Return effective genes all.

    Args:
        sample_id (str): Normalized ``sample_id``.

    Returns:
        Response: Normalized return value.
    """
    try:
        target = str(request.args.get("target") or "").strip().lower() or None
        payload = get_web_api_client().get_json(
            api_endpoints.home_sample(sample_id, "effective_genes", "all"),
            headers=forward_headers(),
            params={"target": target} if target else None,
        )
        return jsonify(
            {
                "items": payload.get("items", []),
                "asp_covered_genes_count": payload.get("asp_covered_genes_count", 0),
                "target": payload.get("target"),
            }
        )
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message=f"Failed to fetch effective genes via API for sample {sample_id}",
        )
        return jsonify({"items": [], "asp_covered_genes_count": 0})


@home_bp.route("/<string:sample_id>/apply_isgl", methods=["POST"])
@login_required
def apply_isgl(sample_id: str) -> tuple[Response, int] | Response:
    """Apply isgl.

    Args:
        sample_id (str): Normalized ``sample_id``.

    Returns:
        tuple[Response, int] | Response: Normalized return value.
    """
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"status": "error", "error": "Invalid payload"}), 400
    isgl_ids = body.get("isgl_ids")
    list_type = str(body.get("list_type") or request.args.get("target") or "snv").strip().lower()
    if not isinstance(isgl_ids, list):
        return jsonify({"status": "error", "error": "Invalid payload"}), 400

    try:
        payload = apply_isgl_api(sample_id, isgl_ids, list_type=list_type)
    except ApiRequestError as exc:
        return _mutation_error(
            exc,
            log_message=f"Failed to apply ISGL via API for sample {sample_id}",
        )

    return jsonify(payload)


@home_bp.route("/<string:sample_id>/adhoc_genes", methods=["POST"])
@login_required
def save_adhoc_genes(sample_id: str) -> tuple[Response, int] | Response:
    """Save adhoc genes.

    Args:
        sample_id (str): Normalized ``sample_id``.

    Returns:
        tuple[Response, int] | Response: Normalized return value.
    """
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"status": "error", "error": "Invalid payload"}), 400
    list_type = str(body.get("list_type") or request.args.get("target") or "snv").strip().lower()

    try:
        payload = save_adhoc_genes_api(
            sample_id,
            genes=body.get("genes", ""),
            label=body.get("label", "adhoc"),
            list_type=list_type,
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
    """Clear adhoc genes.

    Args:
        sample_id (str): Normalized ``sample_id``.

    Returns:
        tuple[Response, int] | Response: Normalized return value.
    """
    try:
        list_type = str(request.args.get("target") or "snv").strip().lower()
        payload = clear_adhoc_genes_api(sample_id, list_type=list_type)
    except ApiRequestError as exc:
        return _mutation_error(
            exc,
            log_message=f"Failed to clear ad-hoc genes via API for sample {sample_id}",
        )

    return jsonify(payload)
