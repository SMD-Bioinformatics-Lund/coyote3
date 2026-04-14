"""
This module defines authentication views for the Coyote3 application.
"""

from flask import (
    Response,
    has_request_context,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask import (
    current_app as app,
)
from flask_login import current_user, login_required, login_user, logout_user

from coyote.blueprints.login import login_bp
from coyote.blueprints.login.forms import LoginForm
from coyote.extensions import login_manager
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    CoyoteApiClient,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import flash_api_failure, flash_api_success
from coyote.services.auth.user_session import User

_SESSION_USER_PAYLOAD_KEY = "auth_user_payload"


def _api_cookie_name() -> str:
    """Api cookie name.

    Returns:
            The  api cookie name result.
    """
    return str(app.config.get("API_SESSION_COOKIE_NAME", "coyote3_api_session"))


def _api_cookie_max_age() -> int:
    """Api cookie max age.

    Returns:
            The  api cookie max age result.
    """
    try:
        return int(app.config.get("API_SESSION_TTL_SECONDS", 12 * 60 * 60))
    except (TypeError, ValueError):
        return 12 * 60 * 60


def _set_api_cookie(response: Response, token: str) -> None:
    """Set api cookie.

    Args:
            response: Response.
            token: Token.

    Returns:
            None.
    """
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
    """Clear api cookie.

    Args:
            response: Response.

    Returns:
            None.
    """
    response.delete_cookie(key=_api_cookie_name(), path="/")


def _extract_session_token(client: CoyoteApiClient) -> str:
    """Extract session token.

    Args:
            client: Client.

    Returns:
            The  extract session token result.
    """
    token = client.last_response_cookie(_api_cookie_name())
    if token:
        return str(token)
    raise ApiRequestError("Authentication backend did not issue a session cookie.")


@login_bp.route("/login", methods=["GET", "POST"])
@login_bp.route("/", methods=["GET", "POST"])
def login() -> str | Response:
    """User login via API-owned authentication."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard_bp.dashboard"))

    form = LoginForm()
    if request.method == "POST" and form.validate_on_submit():
        email = form.username.data.strip()
        password = form.password.data.strip()

        try:
            api_client = get_web_api_client()
            auth_payload = api_client.post_json(
                api_endpoints.auth("sessions"),
                headers=forward_headers(),
                json_body={"username": email, "password": password},
            )
            session_token = _extract_session_token(api_client)
        except ApiRequestError as exc:
            if exc.status_code == 401:
                flash_api_failure("Invalid credentials.", exc)
                app.logger.warning("Login failed: invalid credentials (%s)", email)
            else:
                flash_api_failure("Authentication backend unavailable.", exc)
                app.logger.error("Login API request failed for %s: %s", email, exc)
            return render_template("login.html", form=form)

        user = User(auth_payload.user)
        login_user(user)
        session[_SESSION_USER_PAYLOAD_KEY] = user.to_dict()
        must_change_password = bool(getattr(user, "must_change_password", False))
        response = redirect(
            url_for("profile_bp.change_password", user_id=user.username)
            if must_change_password
            else url_for("dashboard_bp.dashboard")
        )
        _set_api_cookie(response, session_token)
        app.logger.info("User logged in via API: %s (access_level: %s)", email, user.access_level)
        return response

    return render_template("login.html", title="Login", form=form)


@login_bp.route("/logout")
@login_required
def logout() -> Response:
    """Log out the current user and clear API + Flask sessions."""
    try:
        get_web_api_client().delete_json(
            api_endpoints.auth("sessions", "current"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.warning("API logout request failed: %s", exc)

    logout_user()
    session.pop(_SESSION_USER_PAYLOAD_KEY, None)
    response = redirect(url_for("login_bp.login"))
    _clear_api_cookie(response)
    return response


@login_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password() -> str | Response:
    """Start password reset flow."""
    if request.method == "POST":
        username = str(request.form.get("username") or "").strip()
        try:
            get_web_api_client().post_json(
                api_endpoints.auth("password", "reset", "request"),
                headers=forward_headers(),
                json_body={"username": username},
            )
        except ApiRequestError as exc:
            app.logger.warning("Forgot-password request failed for %s: %s", username, exc)
        flash_api_success("If eligible, a password reset email has been sent.")
        return redirect(url_for("login_bp.login"))
    return render_template("forgot_password.html")


@login_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password() -> str | Response:
    """Complete password reset using token."""
    token = str(request.args.get("token") or request.form.get("token") or "").strip()
    if request.method == "POST":
        new_password = str(request.form.get("new_password") or "")
        confirm_password = str(request.form.get("confirm_password") or "")
        if new_password != confirm_password:
            flash_api_failure("Passwords do not match.", ApiRequestError("mismatch"))
            return redirect(url_for("login_bp.reset_password", token=token))
        try:
            get_web_api_client().post_json(
                api_endpoints.auth("password", "reset", "confirm"),
                headers=forward_headers(),
                json_body={"token": token, "new_password": new_password},
            )
            flash_api_success("Password set successfully. Please sign in.")
            return redirect(url_for("login_bp.login"))
        except ApiRequestError as exc:
            flash_api_failure("Unable to set password.", exc)
            return redirect(url_for("login_bp.reset_password", token=token))
    return render_template("reset_password.html", token=token)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """Load user session context from the canonical API session endpoint."""
    try:
        if not has_request_context():
            return None

        # Do not trust cached Flask user payload when API session cookie is missing.
        # This prevents "logged-in UI but 401 API calls" drift after container restarts.
        session_token = request.cookies.get(_api_cookie_name())
        if not session_token:
            session.pop(_SESSION_USER_PAYLOAD_KEY, None)
            return None

        cached_user = session.get(_SESSION_USER_PAYLOAD_KEY)
        if isinstance(cached_user, dict):
            cached_id = str(cached_user.get("_id") or cached_user.get("id") or "")
            if cached_id and cached_id == str(user_id):
                return User(cached_user)

        payload = get_web_api_client().get_json(
            api_endpoints.auth("session"),
            headers=forward_headers(),
        )
        user_payload = payload.user or {}
        api_user_id = str(user_payload.get("_id") or user_payload.get("id") or "")
        if not api_user_id or api_user_id != str(user_id):
            return None
        session[_SESSION_USER_PAYLOAD_KEY] = dict(user_payload)
        return User(user_payload)
    except ApiRequestError:
        return None
    except Exception:
        return None
