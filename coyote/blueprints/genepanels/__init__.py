from flask import Blueprint

# Blueprint configuration
genepanels_bp = Blueprint(
    "genepanels_bp",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="genepanels/static",
)

from coyote.blueprints.genepanels import views  # noqa: F401, E402
