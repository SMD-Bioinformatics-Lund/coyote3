"""Initialize Flask app."""

from flask import Flask, request, redirect, url_for, flash
from flask_cors import CORS
import config
from . import extensions
from .errors import register_error_handlers
from flask_login import current_user, login_user
from coyote.services.auth.user_session import User  # Your User class
from coyote.models.user import UserModel
from coyote.extensions import store
from pymongo.errors import ConnectionFailure
import json


def init_app(testing: bool = False, debug: bool = False) -> Flask:
    """Create Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.jinja_env.add_extension("jinja2.ext.do")
    app.jinja_env.filters["from_json"] = json.loads

    # Allows cross-origin requests for CDM/api
    # /trends needs this to work.
    CORS(app)

    if testing:
        app.logger.info("Testing mode ON.")
        app.logger.info("Loading config.TestConfig")
        app.config.from_object(config.TestConfig())

    elif debug:
        app.logger.warning(
            "Debug mode ON. "
            "(Jag ropar ut mitt innersta hav, jag ropar ut all min skit och allt mitt skav!)"
        )
        app.logger.info("Loading config.DevelopmentConfig")
        app.config.from_object(config.DevelopmentConfig())
        app.debug = True

    else:
        app.logger.info("Loading config.ProductionConfig")
        app.config.from_object(config.ProductionConfig())  # Note initialization of Config

    app.logger.info("Initializing app extensions + blueprints:")
    with app.app_context():
        init_login_manager(app)
        init_db(app)
        init_store(app)
        register_blueprints(app)
        init_ldap(app)
        init_utility(app)
        app.logger.debug("init_db() completed")

        # Cache roles access levels in app context
        app.role_access_levels = {
            role["_id"]: role.get("level", 0) for role in store.roles_handler.get_all_roles()
        }

        # TODO: revit this function and remove unused things
        @app.context_processor
        def inject_user_helpers():
            return {
                "user_has": lambda p: current_user.is_authenticated
                and current_user.has_permission(p),
                "user_is": lambda r: current_user.is_authenticated and current_user.role == r,
                "user_in_group": lambda g: current_user.is_authenticated
                and current_user.in_group(g),
                "pretty_role": lambda r: r.value.replace("_", " ").title(),
                "password_change_enabled": False,
            }

        # Register error handlers
        register_error_handlers(app)

    app.logger.info("App initialization finished. Returning app.")

    # Refresh user session with latest data from the database before each request.
    @app.before_request
    def refresh_user_session():
        if current_user.is_authenticated:
            fresh_user_data = store.user_handler.user_with_id(current_user.username)
            if fresh_user_data:
                role_doc = store.roles_handler.get_role(fresh_user_data.get("role")) or {}
                user_model = UserModel.from_mongo(fresh_user_data, role_doc)
                updated_user = User(user_model)

                # Re-login only if things have changed
                current = current_user.to_dict()
                updated = updated_user.to_dict()

                if current != updated:
                    login_user(updated_user)
                    app.logger.debug(f"Session refreshed: {updated_user.username}")

    @app.before_request
    def enforce_permissions():
        view = app.view_functions.get(request.endpoint)
        if not view:
            return

        # Fetch required metadata
        required_permission = getattr(view, "required_permission", None)
        required_level = getattr(view, "required_access_level", None)
        required_role = getattr(view, "required_role_name", None)

        # If any access control is defined, require authentication
        if required_permission or required_level is not None or required_role:
            if not current_user.is_authenticated:
                flash("Login required", "yellow")
                return redirect(url_for("login_bp.login"))

            # Resolve role level from cached access levels
            resolved_role_level = 0
            if required_role:
                role_levels = app.role_access_levels
                resolved_role_level = role_levels.get(required_role, 0)

            # --------------------------
            # Evaluate all three checks:
            # --------------------------
            permission_ok = (
                required_permission
                and required_permission in current_user.permissions
                and required_permission not in current_user.denied_permissions
            )

            level_ok = required_level is not None and current_user.access_level >= required_level

            role_ok = required_role is not None and current_user.access_level >= resolved_role_level

            if not (permission_ok or level_ok or role_ok):
                flash("You do not have access to this page.", "red")
                return redirect(url_for("home_bp.home_screen"))

    @app.context_processor
    def inject_permission_helpers():
        def can(permission: str) -> bool:
            return (
                current_user.is_authenticated
                and permission in current_user.permissions
                and permission not in current_user.denied_permissions
            )

        def min_level(level: int) -> bool:
            return current_user.is_authenticated and current_user.access_level >= level

        def min_role(role_name: str) -> bool:
            if not current_user.is_authenticated:
                return False

            required_level = app.role_access_levels.get(role_name, 0)
            return current_user.access_level >= required_level

        # 🔥 Store reference to avoid shadowing
        _min_role = min_role
        _min_level = min_level
        _can = can

        def has_access(permission=None, min_role=None, min_level=None) -> bool:
            """Shortcut to check access via permission, role, or level."""
            if not current_user.is_authenticated:
                return False

            if not permission and not min_role and min_level is None:
                return True

            return (
                (permission and _can(permission))
                or (min_role and _min_role(min_role))
                or (min_level is not None and _min_level(min_level))
            )

        return {
            "can": can,
            "min_role": min_role,
            "min_level": min_level,
            "has_access": has_access,
        }

    return app


def init_db(app) -> None:
    app.logger.info("Initializing MongoDB...")

    mongo_uri = app.config.get("MONGO_URI", "not set")
    app.logger.info(f"Connecting to MongoDB at: {mongo_uri}")

    # Initialize the PyMongo extension
    extensions.mongo.init_app(app)

    # Check the connection
    try:
        client = extensions.mongo.cx  # Get PyMongo client
        client.admin.command("ping")  # Basic ping to confirm connection
        app.logger.info("MongoDB connection established successfully.")
    except ConnectionFailure as e:
        app.logger.error(f"MongoDB connection failed: {e}")
        raise RuntimeError("Could not connect to MongoDB. Aborting.") from e


def init_store(app) -> None:
    app.logger.info(f"Initializing MongoAdapter at: {app.config['MONGO_URI']}")
    extensions.store.init_from_app(app)


def init_utility(app) -> None:
    app.logger.info("Initializing Utility")
    extensions.util.init_util()


def register_blueprints(app) -> None:
    app.logger.info("Initializing blueprints")

    def bp_debug_msg(msg):
        app.logger.debug(f"Blueprint registered: {msg}")

    # Coyote main:
    bp_debug_msg("home_bp")
    from coyote.blueprints.home import home_bp

    app.register_blueprint(home_bp, url_prefix="/samples")

    # Login stuff
    bp_debug_msg("login_bp")
    from coyote.blueprints.login import login_bp

    app.register_blueprint(login_bp, url_prefix="/coyote")

    # User Profile Stuff
    bp_debug_msg("profile_bp")
    from coyote.blueprints.userprofile import profile_bp

    app.register_blueprint(profile_bp, url_prefix="/profile")

    # Show Case Variants
    bp_debug_msg("dna_bp")
    from coyote.blueprints.dna import dna_bp

    app.register_blueprint(dna_bp, url_prefix="/dna")

    # Show Case fusions
    bp_debug_msg("rna_bp")
    from coyote.blueprints.rna import rna_bp

    app.register_blueprint(rna_bp, url_prefix="/rna")

    # register common bp
    bp_debug_msg("common_bp")
    from coyote.blueprints.common import common_bp

    app.register_blueprint(common_bp, url_prefix="/")

    # register dashboard bp
    bp_debug_msg("dashboard_bp")
    from coyote.blueprints.dashboard import dashboard_bp

    app.register_blueprint(dashboard_bp, url_prefix="/")

    # register genepanels bp
    bp_debug_msg("genepanels_bp")
    from coyote.blueprints.genepanels import genepanels_bp

    app.register_blueprint(genepanels_bp, url_prefix="/genepanels")

    # register coverage bp
    bp_debug_msg("cov_bp")
    from coyote.blueprints.coverage import cov_bp

    app.register_blueprint(cov_bp, url_prefix="/cov")

    # register admin bp
    bp_debug_msg("admin_bp")
    from coyote.blueprints.admin import admin_bp

    app.register_blueprint(admin_bp, url_prefix="/admin")


def init_login_manager(app) -> None:
    app.logger.debug("Initializing login_manager")
    extensions.login_manager.init_app(app)
    extensions.login_manager.login_view = "login_bp.login"


def init_ldap(app):
    app.logger.debug("Initializing ldap login_manager")
    extensions.ldap_manager.init_app(app)
