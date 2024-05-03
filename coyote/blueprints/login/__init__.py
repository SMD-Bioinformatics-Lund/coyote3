from flask import Blueprint

login_bp = Blueprint("login_bp", __name__)

from coyote.blueprints.login import routes  # noqa: F401, E402
