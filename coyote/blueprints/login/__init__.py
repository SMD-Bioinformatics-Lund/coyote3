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
This module initializes the login blueprint for the Coyote3 project.

- Sets up the Flask blueprint for login-related routes.
- Imports the login views.
- Configures a logger for login events.

Blueprint:
    login_bp: Flask Blueprint for login functionality.

Logger:
    app.login_logger: Logger instance for login events.
"""


from flask import Blueprint
from flask import current_app as app
import logging

login_bp = Blueprint(
    "login_bp", __name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.login import views  # noqa: F401, E402


app.login_logger = logging.getLogger("coyote.login")
