#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#


"""
Coyote3 Meta Information
=====================================
This file serves as the entry point for the Coyote3 application, initializing
the Flask app, configuring extensions, and registering blueprints. It also
handles centralized logging setup for both application and Gunicorn.

Key Responsibilities:
- Initialize and configure the Flask application.
- Set up caching, database, and authentication mechanisms.
- Register blueprints for modular application structure.
- Enforce permissions and access control.
- Provide centralized logging configuration.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from flask import Flask, request, redirect, url_for, flash
from flask_cors import CORS
import config
from coyote import extensions
from .errors import register_error_handlers
from flask_login import current_user, login_user
from coyote.services.auth.user_session import User
from coyote.models.user import UserModel
from coyote.extensions import store
from coyote.util.misc import get_dynamic_assay_nav
from pymongo.errors import ConnectionFailure
from flask_caching import Cache
from typing import Any
import json


# Initialize Flask-Caching
cache = Cache()


def init_app(testing: bool = False, development: bool = False) -> Flask:
    """
    Creates and configures the Flask application instance.

    Initializes the Flask app, loads configuration based on the environment,
    and integrates extensions such as caching, database, authentication, and blueprints.
    Also sets up centralized logging and context processors for user and permission helpers.

    Args:
        testing (bool): If True, loads testing configuration.
        development (bool): If True, loads development configuration and enables debug mode.

    Returns:
        Flask: The configured Flask application instance.
    """
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
        app.debug = True

    elif development:
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
        # Register error handlers
        register_error_handlers(app)

        # Cache roles access levels in app context
        app.role_access_levels = {
            role["_id"]: role.get("level", 0) for role in store.roles_handler.get_all_roles()
        }

        @app.context_processor
        def inject_config():
            """
            Injects the application configuration into the Jinja2 template context.
            """
            return dict(app_config=app.config)

        # Cache assay asp in app context
        @app.context_processor
        def inject_assay_nav() -> dict:
            """
            Flask context processor to inject dynamic assay navigation data into all templates.

            This processor runs automatically during template rendering and makes
            `dynamic_assay_nav` available in the Jinja2 context.

            Behavior:
                - If the user is authenticated, returns a dictionary from `get_dynamic_assay_nav()`.
                - If the user is not authenticated, returns an empty `dynamic_assay_nav` dictionary.

            Returns:
                dict: A dictionary containing `dynamic_assay_nav` for use in templates.
                      Example: {"dynamic_assay_nav": {...}}
            """
            if current_user.is_authenticated:
                return get_dynamic_assay_nav()
            return {"dynamic_assay_nav": {}}

        @app.context_processor
        def inject_build_meta():
            return {
                "APP_VERSION": app.config.get("APP_VERSION"),
                "ENV_NAME": app.config.get("ENV_NAME"),
            }

    # Refresh user session with latest data from the database before each request.
    @app.before_request
    def refresh_user_session() -> None:
        """
        Refreshes the current user's session data before each request.

        This `before_request` hook ensures that any updates to the user's profile, role,
        permissions, or assay access are reflected immediately in the session without requiring logout.

        Behavior:
            - If the user is authenticated:
                - Fetches the latest user document from the database.
                - Rebuilds the `UserModel` with updated role and assay configuration.
                - Compares the current session user data to the freshly loaded data.
                - If changes are detected (e.g., permission updates, role changes):
                    - Re-authenticates the user to update the session state.

        This is useful in environments where user data can change dynamically during a session,
        such as through an admin panel or external provisioning system.

        Returns:
            None
        """
        if current_user.is_authenticated:
            fresh_user_data = store.user_handler.user_with_id(current_user.username)
            if fresh_user_data:
                role_doc = store.roles_handler.get_role(fresh_user_data.get("role")) or {}
                asp_docs = store.asp_handler.get_all_asps(is_active=True)
                user_model = UserModel.from_mongo(fresh_user_data, role_doc, asp_docs)
                updated_user = User(user_model)

                # Re-login only if things have changed
                current = current_user.to_dict()
                updated = updated_user.to_dict()

                if current != updated:
                    login_user(updated_user)
                    app.logger.debug(f"Session refreshed: {updated_user.username}")

    @app.before_request
    def enforce_permissions() -> None:
        """
        Enforces role- or permission-based access control before processing each request.

        This `before_request` hook checks if the target view function has access control metadata
        defined using the `@require(...)` decorator. It then validates whether the current user
        satisfies at least one of the following:

            - Has the required permission (`required_permission`)
            - Meets the required access level (`required_access_level`)
            - Has a role equal to or above the required role (`required_role_name`)

        If the route defines any of these requirements and the user is not authenticated,
        the user is redirected to the login page.

        If the user is authenticated but fails to meet **all** of the defined criteria,
        a flash message is shown and the user is redirected to the default home page.

        Requirements are expected to be attached to view functions via the `@require(...)`
        decorator which sets the following attributes:
            - `required_permission`
            - `required_access_level`
            - `required_role_name`

        Returns:
            None: Either continues processing the request or redirects the user on failure.
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

            level_ok = required_level is not None and current_user.access_level >= required_level

            role_ok = required_role is not None and current_user.access_level >= resolved_role_level

            if not (permission_ok or level_ok or role_ok):
                flash("You do not have access to this page.", "red")
                return redirect(url_for("home_bp.samples_home"))
        return None

    @app.context_processor
    def inject_permission_helpers():
        """
        Injects permission-related helper functions into the Jinja2 template context.

        This context processor provides global utility functions to simplify access control
        logic within templates. These helpers enable you to conditionally render UI elements
        based on permissions, roles, or access levels.

        Injected Template Helpers:
            - `can(permission: str) -> bool`: Returns True if the user has the specified permission
              and it is not explicitly denied.
            - `min_level(level: int) -> bool`: Returns True if the user has an access level ≥ `level`.
            - `min_role(role_name: str) -> bool`: Returns True if the user's role is ≥ the given role.
            - `has_access(permission=None, min_role=None, min_level=None) -> bool`: Returns True if the
              user meets **any** of the provided access criteria.

        Example (Jinja2 Template):
            ```jinja2
            {% if can("samples:view") %}
                <a href="/samples">View Samples</a>
            {% endif %}

            {% if min_level(999) %}
                <span class="badge">Tester or above</span>
            {% endif %}

            {% if has_access(permission="config:edit", min_role="admin") %}
                <a href="/admin/config">Edit Config</a>
            {% endif %}
            ```

        Returns:
            dict[str, Callable]: A dictionary of access-checking functions available in all templates.
        """

        def can(permission: str) -> bool:
            """
            Checks whether the current user has a specific permission.

            This helper is intended for use in Flask templates or internal access checks.
            It confirms that the user is authenticated, explicitly granted the given permission,
            and not explicitly denied it.

            This enables support for fine-grained permission models, where permissions may
            be denied even if granted via role or default assignment.

            Args:
                permission (str): The name of the permission to check (e.g., "samples:edit").

            Returns:
                bool: True if the user is authenticated, has the permission, and it is not denied.
            """

            return (
                current_user.is_authenticated
                and permission in current_user.permissions
                and permission not in current_user.denied_permissions
            )

        def min_level(level: int) -> bool:
            """
            Checks whether the current user meets a minimum access level requirement.

            This function is typically used in templates or access logic to verify that the user:
              - Is authenticated.
              - Has an access level greater than or equal to the specified threshold.

            It supports tiered role-based access control where access levels are numeric
            (e.g., viewer = 1, user = 9, manager = 99, admin = 99999).

            Args:
                level (int): The minimum access level required to access a resource.

            Returns:
                bool: True if the user is authenticated and meets the level requirement; False otherwise.
            """
            return current_user.is_authenticated and current_user.access_level >= level

        def min_role(role_name: str) -> bool:
            """
            Checks whether the current user satisfies a minimum role requirement.

            This function verifies:
              - The user is authenticated.
              - The user's access level is greater than or equal to the level associated with the given role name.

            Role access levels are resolved using `app.role_access_levels`, which maps role names
            (e.g., "viewer", "user", "admin") to numeric levels for hierarchical access enforcement.

            Args:
                role_name (str): The name of the role to check against (e.g., "admin", "group_manager").

            Returns:
                bool: True if the user is authenticated and has an access level ≥ the specified role's level.
                      False otherwise.
            """
            if not current_user.is_authenticated:
                return False

            required_level = app.role_access_levels.get(role_name, 0)
            return current_user.access_level >= required_level

        # Store reference to avoid shadowing
        _min_role = min_role
        _min_level = min_level
        _can = can

        def has_access(permission: str = None, min_role: str = None, min_level: int = None) -> bool:
            """
            Evaluates whether the current user has access based on permission, role, or access level.

            This function serves as a flexible shortcut for checking any combination of:
              - A specific granted permission (not denied).
              - A minimum role, resolved via `app.role_access_levels`.
              - A numeric minimum access level.

            Access is granted if **any** of the provided criteria are satisfied. If no criteria
            are passed, the function defaults to allowing access.

            Args:
                permission (str, optional): A specific permission to check (e.g., "samples:edit").
                min_role (str, optional): The minimum role name required (e.g., "admin").
                min_level (int, optional): The minimum numeric access level required (e.g., 999).

            Returns:
                bool: True if the user is authenticated and satisfies at least one of the access checks,
                      or if no checks are defined. False otherwise.

            Example:
                ```jinja2
                {% if has_access(permission="users:edit", min_role="manager") %}
                    <button>Edit User</button>
                {% endif %}
                ```
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
    Initializes the MongoDB database connection for the Flask application.

    This function sets up the application's connection to MongoDB using
    parameters defined in the Flask config (e.g., `MONGO_URI`, `DB_NAME`).
    It also performs a health check via a `ping` command to ensure the
    database is reachable.

    This function should be called during application startup to ensure
    database availability and to register the connection for later use.

    Args:
        app (Flask): The Flask application instance containing configuration settings.

    Raises:
        RuntimeError: If the database connection or health check (ping) fails.
    """

    app.logger.info("Initializing MongoDB...")

    mongo_uri = app.config.get("MONGO_URI")
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

    Args:
        app (Flask): The Flask application instance.
    """
    app.logger.info(f"Initializing MongoAdapter at: {app.config['MONGO_URI']}")
    extensions.store.init_from_app(app)


def init_utility(app) -> None:
    """
    Initializes utility extensions for the Flask application.

    This function sets up utility extensions required for the application,
    ensuring that all necessary utilities are properly initialized and available
    throughout the app.

    Args:
        app (Flask): The Flask application instance.
    """
    app.logger.info("Initializing Utility")
    extensions.util.init_util()


def register_blueprints(app) -> None:
    """
    Registers all blueprints for the Flask application.

    This function imports and registers each blueprint used in the application.
    Each blueprint represents a module or feature, and is registered with a
    specific URL prefix to organize the application's routes.

    Args:
        app (Flask): The Flask application instance.

    Returns:
        None
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

    app.register_blueprint(login_bp, url_prefix="/")

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

    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

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

    # register docs bp
    bp_debug_msg("docs_bp")
    from coyote.blueprints.docs import docs_bp

    app.register_blueprint(docs_bp, url_prefix="/handbook")


def init_login_manager(app) -> None:
    """
    Initializes the login manager for the Flask application.

    This function sets up the login manager extension for the Flask app and
    specifies the login view to redirect unauthenticated users.

    Args:
        app (Flask): The Flask application instance.
    """
    app.logger.debug("Initializing login_manager")
    extensions.login_manager.init_app(app)
    extensions.login_manager.login_view = "login_bp.login"


def init_ldap(app):
    """
    Initializes the LDAP manager for the Flask application.

    This function sets up the LDAP manager extension for the Flask app,
    enabling integration with an LDAP server for authentication and user management.

    Args:
        app (Flask): The Flask application instance.
    """
    app.logger.debug("Initializing ldap login_manager")
    extensions.ldap_manager.init_app(app)
