
"""
This module defines the user profile views for the Coyote3 project.
"""

from flask import (
    Response,
    abort,
    redirect,
    url_for,
)
from flask_login import current_user, login_required
from coyote.blueprints.userprofile import profile_bp


@profile_bp.route("/<user_id>/view", methods=["GET"])
@login_required
def user_profile(user_id: str) -> str | Response:
    """
    Displays the profile page for the currently logged-in user.

    This view checks if the requested user ID matches the logged-in user's username.
    If not, it returns a 403 Forbidden error. Otherwise, it renders the user's profile
    page using the shared admin view.

    Args:
        user_id (str): The username of the user whose profile is being viewed.

    Returns:
        str | Response: Rendered HTML template for the user's profile page or a Flask Response.
    """
    if user_id != current_user.username:
        abort(403)
    return redirect(url_for("admin_bp.view_user", user_id=user_id))
