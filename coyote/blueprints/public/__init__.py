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
This module initializes the public blueprint for the Coyote3 project.

- Sets up the Flask blueprint for public-facing routes.
- Imports the public views and filters.
- Configures a logger for public events.

Blueprint:
    public_bp: Flask Blueprint for public functionality.

Logger:
    app.public_logger: Logger instance for public events.
"""

from flask import Blueprint
from flask import current_app as app
import logging

# Blueprint configuration
public_bp = Blueprint(
    "public_bp", __name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.public import views  # noqa: F401, E402
from coyote.blueprints.public import filters  # noqa: F401, E402

app.public_logger = logging.getLogger("coyote.public")
