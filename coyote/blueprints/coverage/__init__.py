from flask import Blueprint
from flask import current_app as app
import logging

# Blueprint configuration
cov_bp = Blueprint(
    "cov_bp", __name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.coverage import views  # noqa: F401, E402

app.coverage_logger = logging.getLogger("coyote.coverage")
