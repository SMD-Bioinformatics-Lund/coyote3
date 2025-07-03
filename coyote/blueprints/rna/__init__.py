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
This module initializes the RNA blueprint for the Coyote3 project.

- Sets up the Flask blueprint for RNA-related routes.
- Imports the RNA views.
- Configures a logger for RNA events.

Blueprint:
    rna_bp: Flask Blueprint for RNA functionality.

Logger:
    app.rna_logger: Logger instance for RNA events.
"""

from flask import Blueprint
from flask import current_app as app

# Blueprint configuration
rna_bp = Blueprint(
    "rna_bp", __name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.rna import views  # noqa: F401, E402

app.rna_logger = logging.getLogger("coyote.rna")
