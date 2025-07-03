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
This file defines decorators for logging user actions with audit metadata.
The main decorator, log_action, can be used to wrap Flask route handlers
to automatically log the start, success, and failure of actions, including
metadata and error tracebacks for auditing purposes.
"""

import time
import traceback
from functools import wraps

from flask import g

from coyote.services.audit_logs.logger import AuditLogger


def log_action(action_name: str = None, call_type: str = None) -> callable:
    """
    A Flask-compatible decorator to automatically log audit trail data for user actions.

    This decorator logs when an action starts, succeeds, or fails, and captures metadata for auditing,
    including error tracebacks on failure. It is especially useful for tracking UI or API calls in Flask routes.

    Args:
        action_name (str, optional): Custom action name for audit logs. If not set, defaults to the wrapped function's name.
        call_type (str, optional): Optional label for the origin of the call (e.g., 'UI', 'API').
                                   If set, adds `g.audit_call_type`.

    Behavior:
        - Initializes or extends `g.audit_metadata` (Flask `g` context).
        - On success: logs status, duration, metadata, and optional status code (if returned object has `.status_code`).
        - On exception: logs the failure, exception string, and full traceback to `g.audit_metadata`, then re-raises the exception.
        - Intended to be used where `g.audit_metadata` is populated in advance (e.g., sample_id, user_id).

    Returns:
        Callable: The decorated function with audit logging enabled.

    Example:
        ```python
        @log_action(action_name="delete_sample", call_type="UI")
        def delete_sample(sample_id):
            g.audit_metadata = {"sample_id": sample_id, "user": current_user.username}
            ...
        ```
    """

    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            g.audit_metadata = getattr(g, "audit_metadata", {})
            if call_type:
                g.audit_call_type = call_type

            action = action_name or func.__name__
            logger = AuditLogger()
            start_time = time.perf_counter()

            # Log start
            logger.log(
                action=action, status="started", metadata=g.audit_metadata
            )

            try:
                result = func(*args, **kwargs)
                status_code = getattr(result, "status_code", 200)
                logger.log(
                    action=action,
                    status="success",
                    start_time=start_time,
                    metadata=g.audit_metadata,
                    status_code=status_code,
                )
                return result

            except Exception as e:
                g.audit_metadata["error"] = str(e)
                g.audit_metadata["traceback"] = traceback.format_exc()
                logger.log(
                    action=action,
                    status="failed",
                    start_time=start_time,
                    metadata=g.audit_metadata,
                )
                raise

        return wrapped

    return decorator
