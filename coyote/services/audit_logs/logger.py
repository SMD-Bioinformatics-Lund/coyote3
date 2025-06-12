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

import logging
import json
import time
from functools import wraps
from datetime import datetime
from flask import g, request, has_request_context, session
from flask import current_app as app
from flask_login import current_user


class AuditLogger:
    def __init__(self, logger_name="audit"):
        self.logger = logging.getLogger(logger_name)

    def log(
        self,
        action: str,
        status: str,
        start_time=None,
        metadata: dict = None,
        status_code=None,
    ):
        if not has_request_context():
            return

        user = getattr(current_user, "username", None) or getattr(
            current_user, "email", "anonymous"
        )
        role = getattr(current_user, "role", None)
        route = request.endpoint
        ip = request.remote_addr
        session_id = session.get("_id") if session else None
        call_type = getattr(g, "audit_call_type", None)
        timestamp = datetime.utcnow().isoformat()
        duration_ms = None

        if start_time:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        log_entry = {
            "timestamp": timestamp,
            "level": "INFO",
            "user": user,
            "role": role,
            "action": action,
            "status": status,
            "ip": ip,
            "route": route,
            "call_type": call_type,
            "duration_ms": duration_ms,
            "session_id": session_id,
            "status_code": status_code,
            "extra": metadata or {},
        }

        self.logger.info(json.dumps(log_entry))
