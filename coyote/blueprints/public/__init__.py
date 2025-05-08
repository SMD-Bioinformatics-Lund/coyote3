from flask import Blueprint
from flask import current_app as app

# Blueprint configuration
public_bp = Blueprint("public_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.public import views  # noqa: F401, E402
from coyote.blueprints.public import filters  # noqa: F401, E402

app.public_logger = app.logger.getChild("public")
