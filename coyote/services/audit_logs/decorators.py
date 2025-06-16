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

import time
import traceback
from functools import wraps
from coyote.services.audit_logs.logger import AuditLogger
from flask import g


def log_action(action_name: str = None, call_type: str = None):
    """
    Decorator to log user actions with audit metadata. Attach metadata to g.audit_metadata in the route.
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
