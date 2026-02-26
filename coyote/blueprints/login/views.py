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
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required, login_user, logout_user

from coyote.blueprints.login import login_bp
from coyote.blueprints.login.forms import LoginForm
from coyote.extensions import login_manager
from coyote.services.auth.user_session import User
from coyote.web_api.api_client import ApiRequestError, build_internal_headers, get_web_api_client
from flask_login import current_user


# Login route
@login_bp.route("/login", methods=["GET", "POST"])
@login_bp.route("/", methods=["GET", "POST"])
def login() -> str | Response:
    """
    Handle user login for the Coyote3 application.

    Renders the login form on GET requests. On POST, validates the form,
    authenticates the user using either internal (Coyote3) or LDAP authentication
    based on the user's configured auth type, and logs the user in if credentials
    are valid. Redirects to the home page on success, or re-renders the login form
    with error messages on failure.

    Returns:
        Response: Rendered login template or redirect to home page.
    """
    if current_user.is_authenticated:
        # If user is already authenticated, redirect to the dashboard
        return redirect(url_for("dashboard_bp.dashboard"))
    form = LoginForm()

    if request.method == "POST" and form.validate_on_submit():
        email = form.username.data.strip()
        password = form.password.data.strip()

        try:
            auth_payload = get_web_api_client().authenticate_web_login_internal(
                username=email,
                password=password,
                headers=build_internal_headers(),
            )
        except ApiRequestError:
            flash("Invalid credentials", "red")
            app.logger.warning(f"Login failed: invalid credentials ({email})")
            return render_template("login.html", form=form)

        user = User(auth_payload.user)

        login_user(user)
        app.logger.info(f"User logged in: {email} (access_level: {user.access_level})")

        return redirect(url_for("dashboard_bp.dashboard"))

    return render_template("login.html", title="Login", form=form)


@login_bp.route("/logout")
@login_required
def logout() -> Response:
    """
    Log out the current user and redirect to the login page.

    This view logs out the user using Flask-Login's `logout_user` function,
    then redirects to the login page.

    Returns:
        Response: Redirect to the login page.
    """
    logout_user()
    return redirect(url_for("login_bp.login"))


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """
    Load a user for Flask-Login session management.

    Args:
        user_id (str): The unique identifier of the user.

    Returns:
        User | None: The authenticated User object if found, otherwise None.
    """
    try:
        payload = get_web_api_client().get_user_session_internal(
            user_id=user_id,
            headers=build_internal_headers(),
        )
    except ApiRequestError:
        return None
    return User(payload.user)
