"""
This module initializes the login blueprint for the Coyote3 project.

- Sets up the Flask blueprint for login-related routes.
- Imports the login views.
- Configures a logger for login events.

Blueprint:
    login_bp: Flask Blueprint for login functionality.

Logger:
    app.login_logger: Logger instance for login events.
"""

import logging

from flask import Blueprint
from flask import current_app as app

login_bp = Blueprint("login_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.login import views  # noqa: F401, E402

app.login_logger = logging.getLogger("coyote.login")
