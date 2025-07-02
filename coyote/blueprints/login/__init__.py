import logging

from flask import Blueprint
from flask import current_app as app

login_bp = Blueprint(
    "login_bp", __name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.login import views  # noqa: F401, E402

app.login_logger = logging.getLogger("coyote.login")
