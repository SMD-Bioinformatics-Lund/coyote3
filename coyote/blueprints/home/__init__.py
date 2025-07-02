import logging

from flask import Blueprint
from flask import current_app as app

# Blueprint configuration
home_bp = Blueprint(
    "home_bp", __name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.home import views  # noqa: F401, E402

app.home_logger = logging.getLogger("coyote.home")
