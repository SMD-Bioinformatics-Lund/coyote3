import logging
from functools import wraps
from flask_login import current_user
from flask import request
import json
import traceback
import time


audit_logger = logging.getLogger("audit")


def log_action(action_name: str = None, **extra_info):  # <-- this line is the fix
    """
    Decorator to log actions performed by users.
    Logs include user ID, IP address, action name, status, and any additional info.
    :param action_name: Name of the action being logged. If None, uses the function name.
    :param extra_info: Additional information to log.
    :return: Decorated function.
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user_id = current_user.username if current_user.is_authenticated else "anonymous"
            ip = request.remote_addr
            action = action_name or f.__name__
            safe_kwargs = {
                k: (
                    v
                    if isinstance(v, (str, int, float, bool, type(None)))
                    else str(type(v).__name__)
                )
                for k, v in kwargs.items()
            }

            start_time = time.perf_counter()

            # Log start
            audit_logger.info(
                json.dumps(
                    {
                        "action": action,
                        "user": user_id,
                        "ip": ip,
                        "status": "started",
                        "kwargs": safe_kwargs,
                        **extra_info,
                    }
                )
            )

            try:
                result = f(*args, **kwargs)
                duration = (time.perf_counter() - start_time) * 1000

                # Log success
                audit_logger.info(
                    json.dumps(
                        {
                            "action": action,
                            "user": user_id,
                            "ip": ip,
                            "status": "success",
                            "duration_ms": round(duration, 2),
                            "result_type": str(type(result).__name__),
                            **extra_info,
                        }
                    )
                )

                return result

            except Exception as e:
                duration = (time.perf_counter() - start_time) * 1000

                audit_logger.error(
                    json.dumps(
                        {
                            "action": action,
                            "user": user_id,
                            "ip": ip,
                            "status": "failed",
                            "duration_ms": round(duration, 2),
                            "error": str(e),
                            "traceback": traceback.format_exc(),
                            **extra_info,
                        }
                    )
                )
                raise

        return wrapped

    return decorator
