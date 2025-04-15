from functools import wraps
from flask import abort, g, flash
from flask_login import current_user
from coyote import store


def require_sample_group_access(sample_arg="sample_name"):
    """
    Decorator to enforce group-based access using the sample name from the route.

    Args:
        sample_arg (str): The name of the route argument containing the sample name.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            sample_name = kwargs.get(sample_arg)
            if not sample_name:
                flash(f"Missing `{sample_arg}` in route parameters", "red")
                abort(400, description=f"Missing `{sample_arg}` in route parameters")

            sample = store.sample_handler.get_sample(sample_name)
            if not sample:
                sample = store.sample_handler.get_sample_with_id(sample_name)

            if not sample:
                flash("Sample not found", "red")
                abort(404, description="Sample not found")

            user_groups = set(current_user.groups or [])
            sample_groups = set(sample.get("groups", []))

            if not user_groups & sample_groups:
                flash("Access denied: you do not belong to any of the sample's groups", "red")
                abort(403, description="Access denied: sample group mismatch")

            g.sample = sample
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
