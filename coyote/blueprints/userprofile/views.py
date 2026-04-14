"""User profile routes."""

from __future__ import annotations

from flask import Response, abort, redirect, render_template, request, url_for
from flask import current_app as app
from flask_login import current_user, login_required

from coyote.blueprints.userprofile import profile_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import flash_api_failure, flash_api_success


def _ensure_self(user_id: str) -> None:
    if user_id != current_user.username:
        abort(403)


@profile_bp.route("/<user_id>/view", methods=["GET"])
@login_required
def user_profile(user_id: str) -> str | Response:
    """Render full profile details for the authenticated user."""
    _ensure_self(user_id)
    return redirect(url_for("admin_bp.view_user", user_id=user_id))


@profile_bp.route("/<user_id>/password", methods=["GET", "POST"])
@login_required
def change_password(user_id: str) -> str | Response:
    """Render/process local password change form."""
    _ensure_self(user_id)
    auth_type = str(getattr(current_user, "auth_type", "coyote3") or "coyote3").lower()
    if auth_type != "coyote3":
        flash_api_failure("Password is managed by your identity provider.", ApiRequestError("ldap"))
        return redirect(url_for("profile_bp.user_profile", user_id=user_id))

    if request.method == "POST":
        current_password = str(request.form.get("current_password") or "")
        new_password = str(request.form.get("new_password") or "")
        confirm_password = str(request.form.get("confirm_password") or "")
        if new_password != confirm_password:
            flash_api_failure(
                "New password and confirmation do not match.", ApiRequestError("mismatch")
            )
            return redirect(url_for("profile_bp.change_password", user_id=user_id))
        try:
            get_web_api_client().post_json(
                api_endpoints.auth("password", "change"),
                headers=forward_headers(),
                json_body={
                    "current_password": current_password,
                    "new_password": new_password,
                },
            )
            flash_api_success("Password updated successfully.")
            return redirect(url_for("profile_bp.user_profile", user_id=user_id))
        except ApiRequestError as exc:
            app.logger.warning("Password change failed for user=%s err=%s", user_id, exc)
            flash_api_failure("Unable to change password.", exc)
            return redirect(url_for("profile_bp.change_password", user_id=user_id))

    return render_template("profile_change_password.html", user=current_user)
