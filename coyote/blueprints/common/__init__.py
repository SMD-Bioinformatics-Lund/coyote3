
"""
This module initializes the common blueprint for the Coyote3 Flask application.

- Registers the `common_bp` blueprint with template and static folders.
- Sets up a logger for the common module.
- Imports view handlers for the blueprint.

Intended for use as part of the Coyote3 genomic data analysis framework.
"""

from flask import Blueprint
from flask import current_app as app
import logging

# Blueprint configuration
common_bp = Blueprint(
    name="common_bp",
    import_name=__name__,
    template_folder="templates",
    static_folder="static",
)

from coyote.blueprints.common import views  # noqa: F401, E402

app.common_logger = logging.getLogger("coyote.common")
