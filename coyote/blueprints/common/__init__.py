from flask import Blueprint

# Blueprint configuration
common_bp = Blueprint(
    name="common_bp", import_name=__name__, template_folder="templates", static_folder="static"
)

from coyote.blueprints.common import views  # noqa: F401, E402
