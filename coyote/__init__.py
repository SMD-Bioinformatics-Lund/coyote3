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
- Register request/response lifecycle hooks and helpers.
- Provide centralized logging configuration.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import httpx
from flask import Flask, g, request
from flask_cors import CORS
from flask_login import current_user

import config
from cache_backend import create_cache_backend
from coyote import extensions
from coyote.services.api_client import ApiRequestError
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    build_internal_headers,
    close_web_api_client,
    get_web_api_client,
)
from coyote.util.misc import get_dynamic_assay_nav
from shared.logging import emit_audit_event

from .errors import register_error_handlers


class PrefixMiddleware:
    """
    Respect SCRIPT_NAME-style URL prefixes when the app is served behind a reverse proxy.
    """

    def __init__(self, app, prefix: str):
        """Handle __init__.

        Args:
                app: App.
                prefix: Prefix.
        """
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        """Handle __call__.

        Args:
                environ: Environ.
                start_response: Start response.

        Returns:
                The __call__ result.
        """
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
        init_template_filters(app)
        register_blueprints(app)
        init_utility(app)
        app.logger.debug("Web UI extensions initialized")
        # Register error handlers
        register_error_handlers(app)

        # Cache roles access levels in app context
        app.role_access_levels = {}
        try:
            role_levels_payload = get_web_api_client().get_json(
                api_endpoints.internal("roles", "levels"),
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
            """Handle inject build meta.

            Returns:
                    The inject build meta result.
            """
            return {
                "APP_VERSION": app.config.get("APP_VERSION"),
                "ENV_NAME": app.config.get("ENV_NAME"),
            }

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

    @app.before_request
    def _bind_request_id() -> None:
        """Handle  bind request id.

        Returns:
                None.
        """
        g.request_id = (request.headers.get("X-Request-ID") or "").strip() or str(uuid.uuid4())
        g.request_start = time.perf_counter()

    @app.after_request
    def _log_request(response):
        """Handle  log request.

        Args:
                response: Response.

        Returns:
                The  log request result.
        """
        request_id = getattr(g, "request_id", "-")
        start = getattr(g, "request_start", None)
        duration_ms = ((time.perf_counter() - start) * 1000.0) if start is not None else 0.0
        forwarded_for = (request.headers.get("X-Forwarded-For") or "").strip()
        client_ip = (
            forwarded_for.split(",")[0].strip() if forwarded_for else (request.remote_addr or "N/A")
        )
        user_id = current_user.get_id() if current_user.is_authenticated else "-"
        app.logger.info(
            "ui_request request_id=%s method=%s path=%s status=%s duration_ms=%.2f user=%s ip=%s",
            request_id,
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            user_id,
            client_ip,
        )
        emit_audit_event(
            source="web",
            action="request",
            status="success" if 200 <= int(response.status_code) < 400 else ("error" if int(response.status_code) >= 500 else "failed"),
            severity="error" if int(response.status_code) >= 500 else ("warning" if int(response.status_code) >= 400 else "info"),
            status_code=int(response.status_code),
            duration_ms=round(float(duration_ms), 2),
            method=request.method,
            path=request.path,
            request_id=request_id,
            username=user_id,
            user=user_id,
            role=getattr(current_user, "role", "-") if current_user.is_authenticated else "-",
            ip=client_ip,
        )
        response.headers["X-Request-ID"] = request_id
        return response

    @app.teardown_appcontext
    def _close_api_client(_exc) -> None:
        """Handle  close api client.

        Args:
                _exc:  exc.

        Returns:
                None.
        """
        close_web_api_client()

    # Register shared cache backend (Redis when reachable; disabled backend otherwise).
    app.cache = create_cache_backend(
        config=app.config,
        logger=app.logger,
        namespace="web",
    )
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
