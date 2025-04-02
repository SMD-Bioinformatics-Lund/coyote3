from flask import Blueprint

# Blueprint configuration
admin_bp = Blueprint("admin_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.admin import views  # noqa: F401, E402
from coyote.blueprints.admin import filters  # noqa: F401, E402
