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
Coyote admin views.
"""

from flask import render_template
from coyote.blueprints.admin import admin_bp
from coyote.services.auth.decorators import require
from typing import Any


@admin_bp.route("/")
@require(min_role="manager", min_level=99)
def admin_home() -> Any:
    """
    Renders the admin home page template.
    """
    return render_template("admin_home.html")

