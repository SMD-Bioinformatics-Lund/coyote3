from flask import Blueprint
from flask import current_app as app
import logging

profile_bp = Blueprint(
    "profile_bp", __name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.userprofile import views  # noqa: F401, E402


app.profile_logger = logging.getLogger("coyote.profile")
