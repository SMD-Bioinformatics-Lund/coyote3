import logging

from flask import Blueprint
from flask import current_app as app

# Blueprint configuration
rna_bp = Blueprint(
    "rna_bp", __name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.rna import views  # noqa: F401, E402

app.rna_logger = logging.getLogger("coyote.rna")
