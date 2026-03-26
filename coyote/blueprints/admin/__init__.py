import logging

from flask import Blueprint
from flask import current_app as app

# Blueprint configuration
admin_bp = Blueprint(
    name="admin_bp",
    import_name=__name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="admin/static",
)

from coyote.blueprints.admin import (  # noqa: E402,F401
    views_assay_configs,  # noqa: F401, E402
    views_assay_panels,  # noqa: F401, E402
    views_audit,  # noqa: F401, E402
    views_genelists,  # noqa: F401, E402
    views_home,  # noqa: F401, E402
    views_ingest,  # noqa: F401, E402
    views_permissions,  # noqa: F401, E402
    views_roles,  # noqa: F401, E402
    views_samples,  # noqa: F401, E402
    views_users,  # noqa: F401, E402
)

app.admin_logger = logging.getLogger("coyote.admin")
