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
This module initializes the DNA blueprint for the Coyote3 project.

- Registers the `dna_bp` Flask blueprint for genomic data analysis routes.
- Imports view and filter modules for DNA-related endpoints.
- Configures a dedicated logger for DNA operations.

Blueprint:
    dna_bp: Flask blueprint for DNA-related routes.

Logger:
    app.dna_logger: Logger instance for DNA operations.
"""

from flask import Blueprint
from flask import current_app as app
import logging

# Blueprint configuration
dna_bp = Blueprint("dna_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.dna import views_variants  # noqa: F401, E402
from coyote.blueprints.dna import views_variant_actions  # noqa: F401, E402
from coyote.blueprints.dna import views_cnv  # noqa: F401, E402
from coyote.blueprints.dna import views_transloc  # noqa: F401, E402
from coyote.blueprints.dna import views_reports  # noqa: F401, E402


app.dna_logger = logging.getLogger("coyote.dna")
