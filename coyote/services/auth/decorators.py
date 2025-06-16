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

from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from flask import current_app as app


def require_admin(f):
    """
    Decorator to require admin access.
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


def require_permission(permission: str):
    """
    Requires user to have a specific permission (and not have it denied).
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


def require_any_permission(*permissions):
    """
    Requires user to have at least one of the listed permissions.
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


def require_all_permissions(*permissions):
    """
    Requires user to have all listed permissions.
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


def require_min_access_level(min_level: int):
    """
    Requires user to have at least the given access level.
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


def require_role_or_permission(min_level=None, permission=None):
    """
    Passes if user meets either the role level or has the specific permission.
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


def require(permission=None, min_role=None, min_level=None):
    """
    A decorator to specify access control requirements for a function.
    This decorator allows you to define the required permission, minimum role,
    and minimum access level needed to execute the decorated function. These
    attributes are stored as properties of the function for later use, such as
    during authorization checks.
    Args:
        permission (str, optional): The specific permission required to access
            the function. Defaults to None.
        min_role (str, optional): The minimum role name required to access the
            function. Defaults to None.
        min_level (int, optional): The minimum access level required to access
            the function. Defaults to None.
    Returns:
        function: The decorated function with the access control attributes
        attached.
    """

    def decorator(f):
        f.required_permission = permission
        f.required_access_level = min_level
        f.required_role_name = min_role
        return f

    return decorator
