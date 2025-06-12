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
import logging

# Blueprint configuration
admin_bp = Blueprint(
    name="admin_bp",
    import_name=__name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="admin/static",
)

from coyote.blueprints.admin import views  # noqa: F401, E402
from coyote.blueprints.admin import filters  # noqa: F401, E402

app.admin_logger = logging.getLogger("coyote.admin")
