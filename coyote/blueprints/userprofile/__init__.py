
"""
This module initializes the user profile blueprint for the Coyote3 project.

- Registers the `profile_bp` Flask blueprint for user profile management.
- Imports related views to ensure route registration.
- Sets up a dedicated logger for profile-related operations.

Blueprint:
    profile_bp: Handles user profile routes, templates, and static files.

Logger:
    app.profile_logger: Logger for profile operations under the "coyote.profile" namespace.
"""

from flask import Blueprint
from flask import current_app as app
import logging

profile_bp = Blueprint(
    "profile_bp", __name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.userprofile import views  # noqa: F401, E402


app.profile_logger = logging.getLogger("coyote.profile")
