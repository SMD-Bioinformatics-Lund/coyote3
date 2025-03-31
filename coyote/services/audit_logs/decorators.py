import logging
from functools import wraps
from flask_login import current_user
from flask import request

audit_logger = logging.getLogger("audit")


def log_action(action_name: str):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user_id = current_user.username if current_user.is_authenticated else "anonymous"
            ip = request.remote_addr
            audit_logger.info(f"User '{user_id}' | IP {ip} | Action: {action_name}")
            return f(*args, **kwargs)

        return wrapped

    return decorator
