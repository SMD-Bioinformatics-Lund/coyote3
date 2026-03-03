
from flask import Blueprint
from flask import current_app as app
import logging

# Blueprint configuration
docs_bp = Blueprint(
    "docs_bp",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="docs/static",
)

from coyote.blueprints.docs import views  # noqa: F401, E402


app.docs_logger = logging.getLogger("coyote.docs")
