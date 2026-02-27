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
from flask import Flask, request, redirect, url_for, flash, jsonify
from flask_cors import CORS
import config
from coyote import extensions
from .errors import register_error_handlers
from flask_login import current_user
from coyote.util.misc import get_dynamic_assay_nav
from coyote.integrations.api.api_client import (
    ApiRequestError,
    build_internal_headers,
    get_web_api_client,
)
from flask_caching import Cache
from typing import Any
import json
import os
import httpx
import time


# Initialize Flask-Caching
cache = Cache()


class PrefixMiddleware:
    """
    Respect SCRIPT_NAME-style URL prefixes when the app is served behind a reverse proxy.
    """

    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        if self.prefix:
            path = environ.get("PATH_INFO", "")
            environ["SCRIPT_NAME"] = self.prefix
            if path.startswith(self.prefix):
                environ["PATH_INFO"] = path[len(self.prefix) :] or "/"
        return self.app(environ, start_response)


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
    script_name = os.getenv("SCRIPT_NAME", "").strip().strip('"').strip("'")
    if script_name and script_name != "/":
        # Normalize env input like "coyote3_dev" -> "/coyote3_dev" so URL generation
        # and prefix stripping behave consistently across direct and proxied runs.
        script_name = f"/{script_name.lstrip('/')}".rstrip("/")
        app.config["APPLICATION_ROOT"] = script_name
        app.wsgi_app = PrefixMiddleware(app.wsgi_app, script_name)

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
        init_ldap(app)
        init_template_filters(app)
        register_blueprints(app)
        init_utility(app)
        app.logger.debug("Web UI extensions initialized")
        # Register error handlers
        register_error_handlers(app)

        # Cache roles access levels in app context
        app.role_access_levels = {}
        try:
            role_levels_payload = get_web_api_client().get_role_levels_internal(
                headers=build_internal_headers(),
            )
            app.role_access_levels = dict(role_levels_payload.role_levels)
        except ApiRequestError as exc:
            app.logger.warning("Unable to preload role access levels from API: %s", exc)

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

        def is_api_request() -> bool:
            path = request.path or ""
            app_root = app.config.get("APPLICATION_ROOT", "")
            if app_root and path.startswith(app_root):
                path = path[len(app_root) :] or "/"
            return path == "/api" or path.startswith("/api/")

        def auth_failure_response(status_code: int, message: str):
            if is_api_request():
                return jsonify({"status": status_code, "error": message}), status_code
            flash(message, "yellow" if status_code == 401 else "red")
            if status_code == 401:
                return redirect(url_for("login_bp.login"))
            return redirect(url_for("home_bp.samples_home"))

        # Fetch required metadata
        required_permission = getattr(view, "required_permission", None)
        required_level = getattr(view, "required_access_level", None)
        required_role = getattr(view, "required_role_name", None)

        # UI routes keep authentication gating only.
        # API endpoints are the security authority for RBAC and data access.
        if required_permission or required_level is not None or required_role:
            if not current_user.is_authenticated:
                return auth_failure_response(401, "Login required")
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

            required_level = app.role_access_levels.get(role_name)
            if required_level is None:
                return current_user.role == role_name
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

    verify_external_api_dependency(app)

    # Register the cache with the app
    cache.init_app(app)
    app.cache = cache
    app.logger.info("Flask app initialized successfully.")
    return app


def verify_external_api_dependency(app: Flask) -> None:
    """
    Optionally require an external API runtime before serving web traffic.
    """
    if not app.config.get("REQUIRE_EXTERNAL_API", False):
        return

    api_base = str(app.config.get("API_BASE_URL", "")).rstrip("/")
    api_health_path = app.config.get("API_HEALTH_PATH", "/api/v1/health")
    health_url = f"{api_base}{api_health_path}"
    timeout = httpx.Timeout(3.0, connect=2.0)
    retries = max(1, int(app.config.get("API_HEALTH_RETRIES", 15)))
    retry_interval = float(app.config.get("API_HEALTH_RETRY_INTERVAL_SECONDS", 1.0))
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(health_url)
                response.raise_for_status()
                payload = (
                    response.json()
                    if "application/json" in response.headers.get("content-type", "")
                    else {}
                )
                if isinstance(payload, dict) and payload.get("status") not in ("ok", None):
                    raise RuntimeError(f"Unexpected API health payload: {payload}")
            app.logger.info("External API dependency check passed: %s", health_url)
            return
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                app.logger.warning(
                    "External API dependency check failed (attempt %s/%s): %s (%s). Retrying in %.1fs",
                    attempt,
                    retries,
                    health_url,
                    exc,
                    retry_interval,
                )
                time.sleep(retry_interval)
            else:
                app.logger.error("External API dependency check failed: %s (%s)", health_url, exc)

    # In debug/development, allow the web UI to boot even if API is unavailable.
    is_dev_mode = (
        bool(getattr(app, "debug", False))
        or str(app.config.get("ENV_NAME", "")).strip().lower() == "development"
        or str(os.getenv("DEVELOPMENT", "0")).strip().lower() in {"1", "true", "yes", "on"}
    )
    if is_dev_mode:
        app.logger.warning(
            "External API unavailable in development mode; continuing without strict startup dependency: %s",
            health_url,
        )
        return

    raise RuntimeError(f"External API is required but unavailable: {health_url}") from last_error


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

    app.logger.info("Flask API blueprint removed; using FastAPI service for API routes.")


def init_template_filters(app) -> None:
    """
    Registers all Jinja template filters from a centralized registry.
    """
    app.logger.debug("Initializing template filters")
    from coyote.filters.registry import register_filters

    register_filters(app)


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


def init_ldap(app) -> None:
    """Initialize LDAP manager for the Flask application."""
    app.logger.debug("Initializing ldap login_manager")
    extensions.ldap_manager.init_app(app)
