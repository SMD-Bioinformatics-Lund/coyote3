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


def min_role_required(min_role: str):
    """
    Decorator to check if the user has the required minimum role.
    If the user is not authenticated, they are redirected to the login page.
    If the user does not have the required role, they are redirected to the home screen.
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Login required", "yellow")
                return redirect(url_for("login_bp.login"))

            if not current_user.has_min_role(min_role):
                flash("You don’t have permission to access this page.", "red")
                return redirect(url_for("home_bp.home_screen"))

            return f(*args, **kwargs)

        return wrapped

    return decorator


def access_required(min_role=None, permission=None):
    """
    Decorator to check if the user has the required role or permission.
    If the user is not authenticated, they are redirected to the login page.
    If the user does not have the required role or permission, they are redirected to the home screen.
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Login required.", "yellow")
                return redirect(url_for("login_bp.login"))

            # Pass if either condition is satisfied
            role_ok = min_role and current_user.has_min_role(min_role)
            permission_ok = permission and current_user.can(permission)

            if role_ok or permission_ok:
                return f(*args, **kwargs)

            flash("You do not have permission to access this page.", "red")
            return redirect(url_for("home_bp.home_screen"))

        return wrapped

    return decorator


def permission_required(permission: str):
    """
    Decorator to check if the user has the required permission.
    If the user is not authenticated, they are redirected to the login page.
    If the user does not have the required permission, they are redirected to the home screen.
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Login required", "yellow")
                return redirect(url_for("login_bp.login"))

            if not current_user.can(permission):
                flash("You don’t have permission to perform this action.", "red")
                return redirect(url_for("home_bp.home_screen"))

            return f(*args, **kwargs)

        return wrapped

    return decorator
