"""Admin user-management list and validation routes."""

from flask import Response, flash, jsonify, render_template, request
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)


@admin_bp.route("/users", methods=["GET"])
@login_required
def manage_users() -> str | Response:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("users"),
            headers=forward_headers(),
        )
        users = payload.get("users", [])
        roles = payload.get("roles", {})
    except AttributeError as exc:
        flash(f"Failed to parse users payload: {exc}", "red")
        users = []
        roles = {}
    except ApiRequestError as exc:
        flash(f"Failed to fetch users: {exc}", "red")
        users = []
        roles = {}
    return render_template("users/manage_users.html", users=users, roles=roles)


@admin_bp.route("/users/validate_username", methods=["POST"])
@login_required
def validate_username() -> Response:
    username = request.json.get("username").lower()
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("users", "validate_username"),
            headers=forward_headers(),
            json_body={"username": username},
        )
        exists = bool(payload.get("exists", False))
        return jsonify({"exists": exists})
    except ApiRequestError as exc:
        return jsonify({"exists": False, "error": str(exc)}), 502


@admin_bp.route("/users/validate_email", methods=["POST"])
@login_required
def validate_email():
    email = request.json.get("email").lower()
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("users", "validate_email"),
            headers=forward_headers(),
            json_body={"email": email},
        )
        exists = bool(payload.get("exists", False))
        return jsonify({"exists": exists})
    except ApiRequestError as exc:
        return jsonify({"exists": False, "error": str(exc)}), 502
