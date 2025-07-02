import logging

from flask import Blueprint
from flask import current_app as app

# Blueprint configuration
common_bp = Blueprint(
    name="common_bp",
    import_name=__name__,
    template_folder="templates",
    static_folder="static",
)

from coyote.blueprints.common import views  # noqa: F401, E402

app.common_logger = logging.getLogger("coyote.common")
