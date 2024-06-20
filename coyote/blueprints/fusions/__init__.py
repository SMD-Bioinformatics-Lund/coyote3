from flask import Blueprint

# Blueprint configuration
fusions_bp = Blueprint("fusions_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.fusions import views  # noqa: F401, E402