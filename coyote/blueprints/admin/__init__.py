from flask import Blueprint

# Blueprint configuration
admin_bp = Blueprint("admin_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.admin import views  # noqa: F401, E402
