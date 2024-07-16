from flask import Blueprint

profile_bp = Blueprint("profile_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.userprofile import views  # noqa: F401, E402
