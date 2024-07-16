from flask import Blueprint

login_bp = Blueprint("login_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.login import views  # noqa: F401, E402
