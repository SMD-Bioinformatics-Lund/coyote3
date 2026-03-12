"""
This module initializes the DNA blueprint for the Coyote3 project.

- Registers the `dna_bp` Flask blueprint for genomic data analysis routes.
- Imports view and filter modules for DNA-related endpoints.
- Configures a dedicated logger for DNA operations.

Blueprint:
    dna_bp: Flask blueprint for DNA-related routes.

Logger:
    app.dna_logger: Logger instance for DNA operations.
"""

import logging

from flask import Blueprint
from flask import current_app as app

# Blueprint configuration
dna_bp = Blueprint("dna_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.dna import (
    views_cnv,  # noqa: F401, E402
    views_reports,  # noqa: F401, E402
    views_small_variant_actions,  # noqa: F401, E402
    views_small_variants,  # noqa: F401, E402
    views_transloc,  # noqa: F401, E402
)

app.dna_logger = logging.getLogger("coyote.dna")
