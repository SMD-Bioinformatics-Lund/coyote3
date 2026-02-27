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

"""Admin permission-management list routes."""

from flask import flash, render_template
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


@admin_bp.route("/permissions")
@login_required
def list_permissions() -> str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("permissions"),
            headers=forward_headers(),
        )
        grouped_permissions = payload.grouped_permissions
    except ApiRequestError as exc:
        flash(f"Failed to fetch permissions: {exc}", "red")
        grouped_permissions = {}
    return render_template("permissions/permissions.html", grouped_permissions=grouped_permissions)
