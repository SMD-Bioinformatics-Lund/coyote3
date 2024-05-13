from flask import Blueprint

# Blueprint configuration
variants_bp = Blueprint("variants_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.variants import views  # noqa: F401, E402
