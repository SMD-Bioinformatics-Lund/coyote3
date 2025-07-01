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
This module provides Flask decorators for enforcing access control based on sample or assay group.
Decorators:
    - require_sample_access: Restricts access to users with permission for a specific sample's assay.
    - require_group_access: Restricts access to users belonging to a specified assay group.
"""

from functools import wraps
from flask import abort, g, flash
from flask_login import current_user
from coyote import store


def require_sample_access(sample_arg="sample_name") -> callable:
    """
    Flask route decorator to enforce assay-based sample access control.

    This decorator ensures that:
      - The user is authenticated (implicitly assumed).
      - A sample is fetched from the route parameter (`sample_arg`) via name or ID.
      - The sample exists.
      - The user has access to the sample's assay, based on their allowed `current_user.assays`.

    If any of the above checks fail:
      - An appropriate flash message is shown (for UI feedback).
      - A corresponding HTTP error is raised (`400`, `404`, or `403`).

    Upon success:
      - The matched `sample` object is stored in `flask.g.sample` for downstream use.

    Args:
        sample_arg (str): The name of the route parameter that contains the sample name or ID.
                          Defaults to `"sample_name"`.

    Usage:
        ```python
        @app.route("/samples/<sample_name>/details")
        @require_sample_access("sample_name")
        def sample_details(sample_name):
            sample = g.sample
            ...
        ```

    Returns:
        Callable: The decorated view function with sample access validation.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("You must be logged in to access this resource", "red")
                abort(401, description="Unauthorized: User not authenticated")
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


def require_group_access(group_arg: str = "assay") -> callable:
    """
    Flask route decorator to enforce access control based on assay group membership.

    This decorator ensures that:
      - The currently logged-in user has access to the target group (e.g., assay group) specified in the route.
      - The route must include a parameter (default: "assay") that identifies the group to check.
      - The user must have that group in their `current_user.assay_groups` list.

    If the check fails:
      - A flash message is shown for UI feedback.
      - A 403 Forbidden error is raised with a descriptive message.

    Args:
        group_arg (str): The name of the route argument that contains the target group name.
                         Defaults to `"assay"`.

    Usage:
        ```python
        @app.route("/asp/<assay>/overview")
        @require_group_access("assay")
        def view_assay_panel(assay):
            ...
        ```

    Returns:
        Callable: The decorated route function with enforced group access control.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("You must be logged in to access this resource", "red")
                abort(401, description="Unauthorized: User not authenticated")

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
