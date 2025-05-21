# -*- coding: utf-8 -*-
"""
Meta Information
================

This file serves as the entry point for the Coyote3 application, initializing
the Flask app, configuring extensions, and registering blueprints. It also
handles centralized logging setup for both application and Gunicorn.

Key Responsibilities:
- Initialize and configure the Flask application.
- Set up caching, database, and authentication mechanisms.
- Register blueprints for modular application structure.
- Enforce permissions and access control.
- Provide centralized logging configuration.

Author: Coyote3 Development Team
License: Copyright (c) 2025 Coyote3 Development Team. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from flask import Flask, request, redirect, url_for, flash
from flask_cors import CORS
import config
from . import extensions
from .errors import register_error_handlers
from flask_login import current_user, login_user
from coyote.services.auth.user_session import User
from coyote.models.user import UserModel
from coyote.extensions import store
from coyote.util.misc import get_dynamic_assay_nav
from pymongo.errors import ConnectionFailure
from flask_caching import Cache
from typing import Any
import os
import json


# Initialize Flask-Caching
cache = Cache()


def init_app(testing: bool = False, debug: bool = False) -> Flask:
    """
    Create and configure the Flask application.

    This function initializes a Flask application instance, sets up configurations,
    and integrates various extensions and blueprints.

    :param testing: Flag to indicate if the app is in testing mode.
    :type testing: bool
    :param debug: Flag to indicate if the app is in debug mode.
    :type debug: bool
    :return: Configured Flask application instance.
    :rtype: Flask
    """
    app = Flask(__name__, instance_relative_config=True)
    app.jinja_env.add_extension("jinja2.ext.do")
    app.jinja_env.filters["from_json"] = json.loads

    # Load the configuration for cache
    app.config["CACHE_TYPE"] = "redis"
    app.config["CACHE_REDIS_URL"] = os.getenv(
        "CACHE_REDIS_URL", "redis://redis:6379/0"
    )
    app.config["CACHE_DEFAULT_TIMEOUT"] = 300
    app.config["CACHE_KEY_PREFIX"] = "coyote3_cache"

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
        app.config.from_object(
            config.ProductionConfig()
        )  # Note initialization of Config

    app.logger.info("Initializing app extensions + blueprints:")
    with app.app_context():
        init_login_manager(app)
        init_db(app)
        init_store(app)
        register_blueprints(app)
        init_ldap(app)
        init_utility(app)
        app.logger.debug("init_db() completed")
        # Register error handlers
        register_error_handlers(app)

        # Cache roles access levels in app context
        app.role_access_levels = {
            role["_id"]: role.get("level", 0)
            for role in store.roles_handler.get_all_roles()
        }

        # Cache assay panels in app context
        @app.context_processor
        def inject_assay_nav() -> dict:
            if current_user.is_authenticated:
                return get_dynamic_assay_nav()
            return {"dynamic_assay_nav": {}}

        # TODO: revit this function and remove unused things
        @app.context_processor
        def inject_user_helpers() -> dict[str, Any]:
            """
            Injects user-related helper functions into the Jinja2 template context.

            This context processor provides utility functions for checking user permissions,
            roles, and group memberships, as well as formatting roles for display.

            :return: A dictionary of helper functions for user-related operations.
            :rtype: dict
            """
            return {
                "user_has": lambda p: current_user.is_authenticated
                and current_user.has_permission(p),
                "user_is": lambda r: current_user.is_authenticated
                and current_user.role == r,
                "user_in_group": lambda g: current_user.is_authenticated
                and current_user.in_group(g),
                "pretty_role": lambda r: r.value.replace("_", " ").title(),
                "password_change_enabled": False,
            }

    # Refresh user session with latest data from the database before each request.
    @app.before_request
    def refresh_user_session():
        """
        Refreshes the user session with the latest data from the database.

        This function is executed before each request to ensure that the current user's
        session is updated with the most recent information from the database. If any
        changes are detected in the user's data, the session is refreshed.

        :return: None
        """
        if current_user.is_authenticated:
            fresh_user_data = store.user_handler.user_with_id(
                current_user.username
            )
            if fresh_user_data:
                role_doc = (
                    store.roles_handler.get_role(fresh_user_data.get("role"))
                    or {}
                )
                asp_docs = store.panel_handler.get_all_assay_panels()
                user_model = UserModel.from_mongo(
                    fresh_user_data, role_doc, asp_docs
                )
                updated_user = User(user_model)

                # Re-login only if things have changed
                current = current_user.to_dict()
                updated = updated_user.to_dict()

                if current != updated:
                    login_user(updated_user)
                    app.logger.debug(
                        f"Session refreshed: {updated_user.username}"
                    )

    @app.before_request
    def enforce_permissions():
        """
        Enforces permissions for the current request.

        This function checks if the current user has the required permissions, access level,
        or role to access the requested view. If the user does not meet the requirements,
        they are redirected to the appropriate page.

        :return: None
        """
        view = app.view_functions.get(request.endpoint)
        if not view:
            return None

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

            level_ok = (
                required_level is not None
                and current_user.access_level >= required_level
            )

            role_ok = (
                required_role is not None
                and current_user.access_level >= resolved_role_level
            )

            if not (permission_ok or level_ok or role_ok):
                flash("You do not have access to this page.", "red")
                return redirect(url_for("home_bp.home_screen"))
        return None

    @app.context_processor
    def inject_permission_helpers():
        """
        Injects permission-related helper functions into the Jinja2 template context.

        This context processor provides utility functions for checking user permissions,
        minimum access levels, and roles, as well as a shortcut for combined access checks.

        :return: A dictionary of helper functions for permission-related operations.
        :rtype: dict
        """

        def can(permission: str) -> bool:
            """
            Checks if the current user has a specific permission.

            This function verifies whether the current user is authenticated and has the
            specified permission, ensuring that the permission is not explicitly denied.

            :param permission: The permission to check.
            :type permission: str
            :return: True if the user has the permission, False otherwise.
            :rtype: bool
            """
            return (
                current_user.is_authenticated
                and permission in current_user.permissions
                and permission not in current_user.denied_permissions
            )

        def min_level(level: int) -> bool:
            """
            Checks if the current user has a minimum access level.

            This function verifies whether the current user is authenticated and has an
            access level greater than or equal to the specified level.

            :param level: The minimum access level required.
            :type level: int
            :return: True if the user meets the access level requirement, False otherwise.
            :rtype: bool
            """
            return (
                current_user.is_authenticated
                and current_user.access_level >= level
            )

        def min_role(role_name: str) -> bool:
            """
            Checks if the current user has a minimum role.

            This function verifies whether the current user is authenticated and has an
            access level greater than or equal to the level associated with the specified role.

            :param role_name: The name of the role to check.
            :type role_name: str
            :return: True if the user meets the role requirement, False otherwise.
            :rtype: bool
            """
            if not current_user.is_authenticated:
                return False

            required_level = app.role_access_levels.get(role_name, 0)
            return current_user.access_level >= required_level

        # Store reference to avoid shadowing
        _min_role = min_role
        _min_level = min_level
        _can = can

        def has_access(
            permission: str = None, min_role: str = None, min_level: int = None
        ) -> bool:
            """
            Shortcut to check access via permission, role, or level.

            This function evaluates whether the current user has access based on one or more
            criteria: a specific permission, a minimum role, or a minimum access level. If no
            criteria are provided, it defaults to granting access.

            :param permission: The specific permission to check (optional).
            :type permission: str or None
            :param min_role: The minimum role required for access (optional).
            :type min_role: str or None
            :param min_level: The minimum access level required for access (optional).
            :type min_level: int or None
            :return: True if the user meets any of the specified criteria, False otherwise.
            :rtype: bool
            """
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

    # Register the cache with the app
    cache.init_app(app)
    app.cache = cache
    app.logger.info("Flask app initialized successfully.")
    return app


def init_db(app) -> None:
    """
    Initializes the database connection for the application.

    This function sets up the connection to the MongoDB database using the
    configuration provided in the Flask application instance. It also verifies
    the connection by performing a basic ping operation.

    :param app: The Flask application instance.
    :type app: Flask
    :raises RuntimeError: If the connection to MongoDB fails.
    """
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
    """
    Initializes the data store for the application.

    This function sets up the data store connection using the configuration
    provided in the Flask application instance. It ensures that the store
    is properly initialized and ready for use.

    :param app: The Flask application instance.
    :type app: Flask
    """
    app.logger.info(f"Initializing MongoAdapter at: {app.config['MONGO_URI']}")
    extensions.store.init_from_app(app)


def init_utility(app) -> None:
    """
    Initializes utility extensions for the application.

    This function sets up utility extensions required for the application.
    It ensures that all necessary utilities are properly initialized.

    :param app: The Flask application instance.
    :type app: Flask
    """
    app.logger.info("Initializing Utility")
    extensions.util.init_util()


def register_blueprints(app) -> None:
    """
    Registers all blueprints for the application.

    This function imports and registers all the blueprints used in the application.
    Each blueprint corresponds to a specific module or feature, and they are
    registered with appropriate URL prefixes to organize the application's routes.

    :return: None
    :rtype: None
    """
    app.logger.info("Initializing blueprints")

    def bp_debug_msg(msg):
        """
        Logs a debug message when a blueprint is registered.

        This function is used to log a debug message indicating that a specific
        blueprint has been successfully registered with the Flask application.

        :param msg: The name or identifier of the blueprint being registered.
        :type msg: str
        """
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

    # register coverage bp
    bp_debug_msg("cov_bp")
    from coyote.blueprints.coverage import cov_bp

    app.register_blueprint(cov_bp, url_prefix="/cov")

    # register admin bp
    bp_debug_msg("admin_bp")
    from coyote.blueprints.admin import admin_bp

    app.register_blueprint(admin_bp, url_prefix="/admin")

    # register public bp
    bp_debug_msg("public_bp")
    from coyote.blueprints.public import public_bp

    app.register_blueprint(public_bp, url_prefix="/public")


def init_login_manager(app) -> None:
    """
    Initializes the login manager for the application.

    This function sets up the login manager extension for the Flask application,
    specifying the login view to redirect unauthenticated users.

    :param app: The Flask application instance.
    :type app: Flask
    """
    app.logger.debug("Initializing login_manager")
    extensions.login_manager.init_app(app)
    extensions.login_manager.login_view = "login_bp.login"


def init_ldap(app):
    """
    Initializes the LDAP manager for the application.

    This function sets up the LDAP manager extension for the Flask application,
    allowing integration with an LDAP server for authentication and user management.

    :param app: The Flask application instance.
    :type app: Flask
    """
    app.logger.debug("Initializing ldap login_manager")
    extensions.ldap_manager.init_app(app)
