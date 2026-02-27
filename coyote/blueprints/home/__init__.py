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
This module initializes the Home blueprint for the Coyote3 project.

- Registers the `home_bp` Flask blueprint for home page and dashboard routes.
- Imports view modules for home-related endpoints.
- Configures a dedicated logger for Home operations.

Blueprint:
    home_bp: Flask blueprint for home-related routes.

Logger:
    app.home_logger: Logger instance for Home operations.

"""

from flask import Blueprint
from flask import current_app as app
import logging

# Blueprint configuration
home_bp = Blueprint(
    "home_bp", __name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.home import views  # noqa: F401, E402

app.home_logger = logging.getLogger("coyote.home")
