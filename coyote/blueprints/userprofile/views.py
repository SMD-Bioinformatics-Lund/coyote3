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
This module defines the user profile views for the Coyote3 project.
"""

from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    jsonify,
    Response,
)
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash
from coyote.extensions import store
from coyote.blueprints.userprofile.forms import PasswordChangeForm
from coyote.services.auth.user_session import User
from coyote.blueprints.userprofile import profile_bp
from flask_wtf.csrf import generate_csrf


@profile_bp.route("/", methods=["GET"])
@login_required
def profile() -> str | Response:
    """
    Renders the profile page for the currently logged-in user.

    Returns:
        Response: Rendered HTML template for the user's profile page.
    """
    csrf_token = generate_csrf()

    return render_template(
        "profile.html",
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        groups=current_user.groups,
        fullname=current_user.fullname,
        csrf_token=csrf_token,
    )


# TODO: Should be a ldap call currently disabled
@profile_bp.route("/change-password/<username>", methods=["GET", "POST"])
@login_required
def change_password(username: str) -> Response:
    """
    View to handle password change for a user.

    Args:
        username (str): The username of the user whose password is to be changed.

    Returns:
        Response: Renders the password change form on GET, processes the form on POST.
    """

    form = PasswordChangeForm()
    user = store.user_handler.user_with_id(username)

    if form.validate_on_submit():
        if user and User.validate_login(user.password, form.old_password.data):
            store.user_handler.update_password(
                username,
                generate_password_hash(
                    form.new_password.data,
                    method="pbkdf2:sha256",
                ),
            )
            flash("Password updated successfully", "green")
            return redirect(url_for("profile_bp.profile"))
        else:
            form.old_password.errors.append("Old password is incorrect")

    return render_template(
        "change_password.html", form=form, username=username
    )


@profile_bp.route("/update-info", methods=["POST"])
@login_required
def update_info() -> Response:
    """
    Update the current user's profile information.

    This view handles updates to the user's full name and, if the user is an admin,
    also allows updating the user's group memberships. The request must be a POST
    with a JSON payload containing the fields to update.

    Request JSON Example:
        {
            "fullname": "New Full Name",
            "groups": ["group1", "group2"]  # Optional, admin only
        }

    Returns:
        Response: A JSON response indicating success.
    """
    data = request.get_json() or {}

    user_id = current_user.username
    fullname = data.get("fullname", "").strip()
    groups = data.get("groups", [])

    if fullname:
        store.user_handler.update_user_fullname(user_id, fullname)

    if current_user.is_admin and isinstance(groups, list):
        store.user_handler.update_user_groups(user_id, groups)

    # Optionally update timestamp
    store.user_handler.update_user_timestamp(user_id, field="updated")

    return jsonify({"status": "success"})
