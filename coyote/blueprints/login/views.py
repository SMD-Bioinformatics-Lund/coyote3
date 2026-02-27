#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
This module defines authentication views for the Coyote3 application.
"""

from flask import (
    Response,
    current_app as app,
    flash,
    has_request_context,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from coyote.blueprints.login import login_bp
from coyote.blueprints.login.forms import LoginForm
from coyote.extensions import login_manager
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.auth.user_session import User


def _api_cookie_name() -> str:
    return str(app.config.get("API_SESSION_COOKIE_NAME", "coyote3_api_session"))


def _api_cookie_max_age() -> int:
    try:
        return int(app.config.get("API_SESSION_TTL_SECONDS", 12 * 60 * 60))
    except (TypeError, ValueError):
        return 12 * 60 * 60


def _set_api_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_api_cookie_name(),
        value=str(token),
        httponly=True,
        secure=bool(app.config.get("SESSION_COOKIE_SECURE", False)),
        samesite="Lax",
        max_age=_api_cookie_max_age(),
        path="/",
    )


def _clear_api_cookie(response: Response) -> None:
    response.delete_cookie(key=_api_cookie_name(), path="/")


@login_bp.route("/login", methods=["GET", "POST"])
@login_bp.route("/", methods=["GET", "POST"])
def login() -> str | Response:
    """Handle user login via API-owned authentication."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard_bp.dashboard"))

    form = LoginForm()
    if request.method == "POST" and form.validate_on_submit():
        email = form.username.data.strip()
        password = form.password.data.strip()

        try:
            auth_payload = get_web_api_client().post_json(
                api_endpoints.auth("login"),
                headers=forward_headers(),
                json_body={"username": email, "password": password},
            )
        except ApiRequestError as exc:
            if exc.status_code == 401:
                flash("Invalid credentials", "red")
                app.logger.warning("Login failed: invalid credentials (%s)", email)
            else:
                flash("Authentication backend unavailable.", "red")
                app.logger.error("Login API request failed for %s: %s", email, exc)
            return render_template("login.html", form=form)

        user = User(auth_payload.user)
        login_user(user)

        response = redirect(url_for("dashboard_bp.dashboard"))
        _set_api_cookie(response, auth_payload.session_token)
        app.logger.info("User logged in via API: %s (access_level: %s)", email, user.access_level)
        return response

    return render_template("login.html", title="Login", form=form)


@login_bp.route("/logout")
@login_required
def logout() -> Response:
    """Log out the current user and clear API + Flask sessions."""
    try:
        get_web_api_client().post_json(
            api_endpoints.auth("logout"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.warning("API logout request failed: %s", exc)

    logout_user()
    response = redirect(url_for("login_bp.login"))
    _clear_api_cookie(response)
    return response


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """Load user session context from API `/auth/me` only."""
    try:
        if not has_request_context():
            return None

        payload = get_web_api_client().get_json(
            api_endpoints.auth("me"),
            headers=forward_headers(),
        )
        user_payload = payload.user or {}
        api_user_id = str(user_payload.get("_id") or user_payload.get("id") or "")
        if not api_user_id or api_user_id != str(user_id):
            return None
        return User(user_payload)
    except ApiRequestError:
        return None
    except Exception:
        return None
