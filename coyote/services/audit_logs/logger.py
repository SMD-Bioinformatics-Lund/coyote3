import json
import logging
import time
from datetime import datetime
from functools import wraps

from flask import current_app as app
from flask import g, has_request_context, request, session
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
