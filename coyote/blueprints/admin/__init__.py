from flask import Blueprint
from flask import current_app as app
import logging

# Blueprint configuration
admin_bp = Blueprint(
    name="admin_bp",
    import_name=__name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="admin/static",
)

from coyote.blueprints.admin import views  # noqa: F401, E402
from coyote.blueprints.admin import filters  # noqa: F401, E402

app.admin_logger = logging.getLogger("coyote.admin")
