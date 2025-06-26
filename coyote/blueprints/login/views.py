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
from flask_login import login_user, logout_user

from coyote.blueprints.login import login_bp
from coyote.blueprints.login.forms import LoginForm
from coyote.extensions import ldap_manager, login_manager, store
from coyote.models.user import UserModel
from coyote.services.auth.user_session import User


# Login route
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
    form = LoginForm()

    if request.method == "POST" and form.validate_on_submit():
        email = form.username.data.strip()
        password = form.password.data.strip()

        # Fetch user
        user_doc = store.user_handler.user(email)
        if not user_doc or not user_doc.get("is_active", True):
            flash("User not found or inactive.", "red")
            app.logger.warning(
                f"Login failed: user not found or inactive ({email})"
            )
            return render_template("login.html", form=form)

        # Authenticate
        use_internal = user_doc.get("auth_type") == "coyote3"
        valid = (
            UserModel.validate_login(user_doc["password"], password)
            if use_internal
            else ldap_authenticate(email, password)
        )

        if not valid:
            flash("Invalid credentials", "red")
            app.logger.warning(f"Login failed: invalid credentials ({email})")
            return render_template("login.html", form=form)

        # Merge role + build user model
        role_doc = store.roles_handler.get_role(user_doc.get("role")) or {}
        user_model = UserModel.from_mongo(user_doc, role_doc)
        user = User(user_model)

        # Login and update last login timestamp
        login_user(user)
        store.user_handler.update_user_last_login(user_doc["_id"])
        app.logger.info(
            f"User logged in: {email} (access_level: {user.access_level})"
        )

        return redirect(url_for("dashboard_bp.dashboard"))

    return render_template("login.html", title="Login", form=form)


@login_bp.route("/logout")
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
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        return None

    role_doc = store.roles_handler.get_role(user_doc.get("role")) or {}
    user_model = UserModel.from_mongo(user_doc, role_doc)
    return User(user_model)


def ldap_authenticate(username: str, password: str) -> bool:
    """
    Authenticate a user against the configured LDAP server.

    Args:
        username (str): The username or login identifier.
        password (str): The user's password.

    Returns:
        bool: True if authentication succeeds, False otherwise.
    """
    authorized = False

    try:
        authorized = ldap_manager.authenticate(
            username=username,
            password=password,
            base_dn=app.config.get("LDAP_BASE_DN")
            or app.config.get("LDAP_BINDDN"),
            attribute=app.config.get("LDAP_USER_LOGIN_ATTR"),
        )
    except Exception as ex:
        flash(str(ex), "red")

    return authorized
