from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


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
            return redirect(url_for("home_bp.home_screen"))

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
                flash("You don’t have permission to perform this action.", "red")
                return redirect(url_for("home_bp.home_screen"))

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

            if not any(p in current_user.granted_permissions for p in permissions):
                flash("You don’t have any of the required permissions.", "red")
                return redirect(url_for("home_bp.home_screen"))

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

            missing = [p for p in permissions if p not in current_user.granted_permissions]
            if missing:
                flash(f"Missing permissions: {', '.join(missing)}", "red")
                return redirect(url_for("home_bp.home_screen"))

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
                return redirect(url_for("home_bp.home_screen"))

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

            role_ok = min_level is not None and current_user.has_min_access_level(min_level)
            permission_ok = (
                permission is not None and permission in current_user.granted_permissions
            )

            if role_ok or permission_ok:
                return f(*args, **kwargs)

            flash("You do not have access to this page.", "red")
            return redirect(url_for("home_bp.home_screen"))

        return wrapped

    return decorator


def require(permission=None, min_level=None, min_role=None):
    """
    Assigns permission and/or min role requirement to a route.
    Accepts either access level or role name (resolved via roles_handler).
    """

    def decorator(f):
        f.required_permission = permission

        resolved_level = min_level

        if min_role and not min_level:
            # resolve access level from role name
            roles_handler = getattr(app, "roles_handler", None) or app.extensions.get(
                "roles_handler"
            )
            if roles_handler:
                role_doc = roles_handler.get_role(min_role)
                resolved_level = role_doc.get("level") if role_doc else 0

        f.required_access_level = resolved_level
        return f

    return decorator
