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
Access control decorators for Flask route handlers in the Coyote3 project.

This module provides decorators to enforce authentication, admin status,
permission checks, and access level requirements for Flask views.
"""

from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


def require_admin(f) -> callable:
    """
    Flask route decorator to restrict access to admin users only.

    This decorator ensures that:
      - The user is authenticated.
      - The user has administrative privileges (`current_user.is_admin` is True).

    If either condition fails:
      - The user is flashed a warning or error message.
      - They are redirected to the login page (if unauthenticated), or to the home page (if not an admin).

    Usage:
        Apply to Flask route handlers to protect routes meant for admin users only.

    Example:
        ```python
        @app.route("/admin/dashboard")
        @require_admin
        def admin_dashboard():
            return render_template("admin/dashboard.html")
        ```

    Returns:
        Callable: The decorated view function with admin access control enforced.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Login required", "yellow")
            return redirect(url_for("login_bp.login"))

        if not current_user.is_admin:
            flash("Admins only!", "red")
            return redirect(url_for("home_bp.samples_home"))

        return f(*args, **kwargs)

    return decorated_function


def require_permission(permission: str) -> callable:
    """
    Flask route decorator to enforce permission-based access control.

    This decorator ensures that the currently logged-in user:
      - Is authenticated.
      - Has the specified `permission` in their granted permissions.
      - Is not explicitly denied access via their permissions model (handled externally).

    If either condition fails:
      - The user is shown a flash message.
      - They are redirected to the login page (if unauthenticated), or to the home page (if unauthorized).

    Args:
        permission (str): The permission string required to access the route (e.g., "config:edit", "samples:view").

    Usage:
        Apply to Flask route handlers where granular access control is required based on permissions.

    Example:
        ```python
        @app.route("/assay-configs/<config_id>/edit")
        @require_permission("config:edit")
        def edit_assay_config(config_id):
            ...
        ```

    Returns:
        Callable: The decorated route function with permission enforcement.
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Login required.", "yellow")
                return redirect(url_for("login_bp.login"))

            if permission not in current_user.granted_permissions:
                flash(
                    "You don’t have permission to perform this action.", "red"
                )
                return redirect(url_for("home_bp.samples_home"))

            return f(*args, **kwargs)

        return wrapped

    return decorator


def require_any_permission(*permissions) -> callable:
    """
    Flask route decorator to enforce access control based on at least one required permission.

    This decorator ensures that the currently logged-in user:
      - Is authenticated.
      - Has at least one of the specified permissions in `current_user.granted_permissions`.

    If the user is not authenticated or lacks all of the listed permissions:
      - A flash message is shown.
      - The user is redirected to the login page (if unauthenticated) or the home page (if unauthorized).

    Args:
        *permissions (str): One or more permission strings (e.g., "samples:view", "config:edit").

    Usage:
        Apply to Flask route handlers where access should be granted if the user has **any** one of several permissions.

    Example:
        ```python
        @app.route("/reports/export")
        @require_any_permission("reports:export", "admin:override")
        def export_report():
            ...
        ```

    Returns:
        Callable: The decorated route function with multi-permission access control.
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Login required.", "yellow")
                return redirect(url_for("login_bp.login"))

            if not any(
                p in current_user.granted_permissions for p in permissions
            ):
                flash("You don’t have any of the required permissions.", "red")
                return redirect(url_for("home_bp.samples_home"))

            return f(*args, **kwargs)

        return wrapped

    return decorator


def require_all_permissions(*permissions) -> callable:
    """
    Flask route decorator to enforce strict permission-based access control.

    This decorator ensures that the currently logged-in user:
      - Is authenticated.
      - Possesses **all** of the specified permissions.

    If the user is not authenticated or is missing any required permissions:
      - A flash message is shown.
      - The user is redirected to the login page (if unauthenticated) or to the home page (if unauthorized).
      - Missing permissions are listed in the error message for transparency.

    Args:
        *permissions (str): One or more permission strings the user must have (e.g., "config:edit", "samples:delete").

    Usage:
        Apply to Flask route handlers that should only be accessible if all listed permissions are granted.

    Example:
        ```python
        @app.route("/admin/users/<user_id>/delete")
        @require_all_permissions("users:delete", "audit:write")
        def delete_user(user_id):
            ...
        ```

    Returns:
        Callable: The decorated route function with all-permission enforcement.
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Login required.", "yellow")
                return redirect(url_for("login_bp.login"))

            missing = [
                p
                for p in permissions
                if p not in current_user.granted_permissions
            ]
            if missing:
                flash(f"Missing permissions: {', '.join(missing)}", "red")
                return redirect(url_for("home_bp.samples_home"))

            return f(*args, **kwargs)

        return wrapped

    return decorator


def require_min_access_level(min_level: int) -> callable:
    """
    Flask route decorator to enforce role-based access using a minimum access level.

    This decorator ensures that the currently logged-in user:
      - Is authenticated.
      - Has an access level greater than or equal to the specified `min_level`.

    If the user is not authenticated or has insufficient access level:
      - A flash message is shown.
      - The user is redirected to the login page (if unauthenticated) or to the home page (if unauthorized).

    Args:
        min_level (int): The minimum numeric access level required to access the route.
                         Higher numbers represent higher privilege (e.g., viewer=1, user=9, admin=99999).

    Usage:
        Apply to Flask route handlers where access should be restricted to users at or above a certain role level.

    Example:
        ```python
        @app.route("/admin/settings")
        @require_min_access_level(99999)  # Admins only
        def settings():
            ...
        ```

    Returns:
        Callable: The decorated route function with enforced access level check.
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Login required.", "yellow")
                return redirect(url_for("login_bp.login"))

            if not current_user.has_min_access_level(min_level):
                flash("Insufficient role level to access this page.", "red")
                return redirect(url_for("home_bp.samples_home"))

            return f(*args, **kwargs)

        return wrapped

    return decorator


def require_role_or_permission(min_level=None, permission=None) -> callable:
    """
    Flask route decorator that grants access if the user satisfies either a minimum access level
    or holds a specific permission.

    This flexible access control mechanism is useful for routes that should be accessible to
    either high-privilege roles (e.g., admin, manager) or users with explicitly granted permissions.

    Conditions:
      - The user must be authenticated.
      - Access is granted if:
        - `min_level` is provided and `current_user` has an access level ≥ `min_level`, **OR**
        - `permission` is provided and `permission` is in `current_user.granted_permissions`.

    If the user is not authenticated or fails both checks:
      - A flash message is shown.
      - The user is redirected to the login page (if unauthenticated) or to the home page (if unauthorized).

    Args:
        min_level (int, optional): Minimum access level required (e.g., viewer=1, admin=99999).
        permission (str, optional): Specific permission string required (e.g., "samples:edit").

    Usage:
        Apply to Flask route handlers where access should be granted to either privileged roles or
        users with a specific permission.

    Example:
        ```python
        @app.route("/reports/approve")
        @require_role_or_permission(min_level=999, permission="reports:approve")
        def approve_reports():
            ...
        ```

    Returns:
        Callable: The decorated route function with combined role/permission-based access control.
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Login required.", "yellow")
                return redirect(url_for("login_bp.login"))

            role_ok = (
                min_level is not None
                and current_user.has_min_access_level(min_level)
            )
            permission_ok = (
                permission is not None
                and permission in current_user.granted_permissions
            )

            if role_ok or permission_ok:
                return f(*args, **kwargs)

            flash("You do not have access to this page.", "red")
            return redirect(url_for("home_bp.samples_home"))

        return wrapped

    return decorator


def require(permission=None, min_role=None, min_level=None) -> callable:
    """
    Decorator to annotate a function with access control requirements for external enforcement.

    Unlike typical decorators that perform the access check directly, this decorator **does not block execution**.
    Instead, it attaches metadata to the function for later inspection — e.g., by a global `before_request` hook
    or an access control layer.

    This is useful in systems where route-level access control is centralized and uses route attributes
    to determine if the current user has access.

    Args:
        permission (str, optional): A specific permission required to access the function
            (e.g., "view_samples").
        min_role (str, optional): The minimum role name required to access the function
            (e.g., "admin", "manager").
        min_level (int, optional): The minimum numeric access level required (e.g., 99999 for admin).

    Behavior:
        The specified values are stored as attributes on the decorated function:
            - `required_permission`
            - `required_role_name`
            - `required_access_level`

        These can then be read during runtime authorization.

    Usage:
        ```python
        @require(permission="view_samples", min_level=9)
        def view_samples():
            ...
        ```

    Returns:
        function: The original function with access control metadata attached.
    """

    def decorator(f):
        f.required_permission = permission
        f.required_access_level = min_level
        f.required_role_name = min_role
        return f

    return decorator
