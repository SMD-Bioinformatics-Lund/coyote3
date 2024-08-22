from flask import Blueprint
from logging import getLogger
from flask import current_app as app

# Blueprint configuration
genepanels_bp = Blueprint(
    "genepanels_bp",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="genepanels/static",
)
from coyote.blueprints.genepanels import views  # noqa: F401, E402

app.genepanels_logger = getLogger("genepanels")
