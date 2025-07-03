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

from flask import Blueprint
from flask import current_app as app

# Blueprint configuration
dashboard_bp = Blueprint(
    "dashboard_bp",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="dashboard/static",
)

# print(dashboard_bp.static)
from coyote.blueprints.dashboard import views  # noqa: F401, E402

app.dashboard_logger = logging.getLogger("coyote.dashboard")
