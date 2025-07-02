from functools import wraps

from flask import abort, flash, g
from flask_login import current_user

from coyote import store


def require_sample_access(sample_arg="sample_name"):
    """
    Decorator to enforce assay-based access using the sample name from the route.

    Args:
        sample_arg (str): The name of the route argument containing the sample name.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            sample_name = kwargs.get(sample_arg)
            if not sample_name:
                flash(f"Missing `{sample_arg}` in route parameters", "red")
                abort(
                    400,
                    description=f"Missing `{sample_arg}` in route parameters",
                )

            sample = store.sample_handler.get_sample(sample_name)
            if not sample:
                sample = store.sample_handler.get_sample_by_id(sample_name)

            if not sample:
                flash("Sample not found", "red")
                abort(404, description="Sample not found")

            user_assays = set(current_user.assays or [])
            sample_assay = sample.get("assay", "")

            if sample_assay not in user_assays:
                flash(
                    "Access denied: you do not belong to any of the sample's groups",
                    "red",
                )
                abort(403, description="Access denied: sample assay mismatch")

            g.sample = sample
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def require_group_access(group_arg: str = "assay"):
    """
    Decorator to enforce assay-based access control.

    Args:
        group_arg (str): The name of the route argument that contains the target group name.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user_assay_groups = set(current_user.assay_groups or [])
            target_group = kwargs.get(group_arg)

            if not target_group or target_group not in user_assay_groups:
                flash(
                    "Access denied: You do not have permission to access this assay.",
                    "red",
                )
                abort(
                    403,
                    description="Access denied: You do not belong to the target assay.",
                )

            return view_func(*args, **kwargs)

        return wrapper

    return decorator
