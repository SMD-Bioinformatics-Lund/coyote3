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
    Response,
    abort,
)
from flask_login import current_user, login_required
from coyote.blueprints.admin.views import view_user
from coyote.blueprints.userprofile import profile_bp


@profile_bp.route("/<user_id>/view", methods=["GET"])
@login_required
def user_profile(user_id: str) -> str | Response:
    """
    Renders the profile page for the currently logged-in user.

    This view retrieves the user's profile information and renders it in a template.
    It requires the user to be logged in.

    Returns:
        Response: Rendered HTML template for the user's profile page.
    """
    # Fetch user from DB (if needed)
    if user_id != current_user.username:
        abort(403)
    return view_user(user_id)
