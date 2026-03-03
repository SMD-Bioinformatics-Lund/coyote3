
"""
Coyote admin views.
"""

from flask import render_template
from flask_login import login_required
from coyote.blueprints.admin import admin_bp
from typing import Any


@admin_bp.route("/")
@login_required
def admin_home() -> Any:
    """
    Renders the admin home page template.
    """
    return render_template("admin_home.html")

