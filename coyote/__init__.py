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


def init_app(testing: bool = False, debug: bool = False) -> Flask:
    """Create Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.jinja_env.add_extension("jinja2.ext.do")

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
        if not current_user.is_authenticated:
            return

        view = app.view_functions.get(request.endpoint)
        if not view:
            return

        required_permission = getattr(view, "required_permission", None)
        required_level = getattr(view, "required_access_level", None)

        # Permission check
        if required_permission:
            if required_permission not in current_user.permissions:
                flash("You lack the required permission to access this page.", "red")
                return redirect(url_for("home_bp.home_screen"))

            if required_permission in current_user.denied_permissions:
                flash("Access to this permission is explicitly forbidden.", "red")
                return redirect(url_for("home_bp.home_screen"))

        # Access level check
        if required_level is not None:
            if not current_user.has_min_access_level(required_level):
                flash("Your role does not allow access to this page.", "red")
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

            role_doc = store.roles_handler.get_role(role_name)
            required_level = role_doc.get("level") if role_doc else 0
            return current_user.access_level >= required_level

        return {"can": can, "min_level": min_level, "min_role": min_role}

    return app


def init_db(app) -> None:
    app.logger.info("Initializing MongoDB")
    # TODO: Add connection checks
    app.logger.info("Initializing mongodb at: " f"{app.config['MONGO_URI']}")
    extensions.mongo.init_app(app)


def init_store(app) -> None:
    app.logger.info("Initializing MongoAdapter at: " f"{app.config['MONGO_URI']}")
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

    app.register_blueprint(common_bp, url_prefix="/common")

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
