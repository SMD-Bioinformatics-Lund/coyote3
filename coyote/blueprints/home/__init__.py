from flask import Blueprint

# Blueprint configuration
home_bp = Blueprint("home_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.home import views  # noqa: F401, E402
