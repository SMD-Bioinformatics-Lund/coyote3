from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


def require_admin(f):
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


def role_required(allowed_roles: list):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Login required", "yellow")
                return redirect(url_for("login_bp.login"))

            if current_user.role not in allowed_roles:
                flash("You don’t have permission to access this page.", "red")
                return redirect(url_for("home_bp.home_screen"))

            return f(*args, **kwargs)

        return wrapped

    return decorator


def permission_required(permission: str):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Login required", "yellow")
                return redirect(url_for("login_bp.login"))

            if not current_user.has_permission(permission):
                flash("You don’t have permission to perform this action.", "red")
                return redirect(url_for("home_bp.home_screen"))

            return f(*args, **kwargs)

        return wrapped

    return decorator
