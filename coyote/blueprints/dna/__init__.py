from flask import Blueprint
from flask import current_app as app
import logging

# Blueprint configuration
dna_bp = Blueprint(
    "dna_bp", __name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.dna import views  # noqa: F401, E402
from coyote.blueprints.dna import filters  # noqa: F401, E402


app.dna_logger = logging.getLogger("coyote.dna")
