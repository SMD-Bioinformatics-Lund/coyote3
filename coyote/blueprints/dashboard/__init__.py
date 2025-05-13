from flask import Blueprint
from flask import current_app as app
import logging

# Blueprint configuration
dashboard_bp = Blueprint(
    "dashboard_bp",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="dashboard/static",
)

# print(dashboard_bp.static)
from coyote.blueprints.dashboard import views  # noqa: F401, E402


app.dashboard_logger = logging.getLogger("coyote.dashboard")
