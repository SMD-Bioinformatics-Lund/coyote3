"""
This module initializes the RNA blueprint for the Coyote3 project.

- Sets up the Flask blueprint for RNA-related routes.
- Imports the RNA views.
- Configures a logger for RNA events.

Blueprint:
    rna_bp: Flask Blueprint for RNA functionality.

Logger:
    app.rna_logger: Logger instance for RNA events.
"""

import logging

from flask import Blueprint
from flask import current_app as app

# Blueprint configuration
rna_bp = Blueprint("rna_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.rna import (
    views_fusions,  # noqa: F401, E402
    views_reports,  # noqa: F401, E402
)

app.rna_logger = logging.getLogger("coyote.rna")
