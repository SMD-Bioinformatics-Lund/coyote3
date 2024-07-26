from flask import Blueprint

# Blueprint configuration
dna_bp = Blueprint("dna_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.dna import views  # noqa: F401, E402
