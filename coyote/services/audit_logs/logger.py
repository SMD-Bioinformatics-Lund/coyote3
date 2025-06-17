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
Coyote3 Audit Logger Module
=====================

This module defines the `AuditLogger` class, which provides structured audit logging
for user actions and API requests within the application. It captures contextual
information such as user identity, role, route, IP address, session, and timing.

The logger is intended to be used across the application to ensure consistent
and comprehensive audit trails for security and compliance purposes.
"""

import logging
import json
import time
from functools import wraps
from datetime import datetime
from flask import g, request, has_request_context, session
from flask import current_app as app
from flask_login import current_user


class AuditLogger:
    """
    AuditLogger provides structured logging of user actions and application events
    in a Flask-based web application. Logs are serialized as JSON strings, making
    them easily searchable, indexable, and parsable by log processors and audit tools.

    Attributes:
        logger (logging.Logger): The underlying logger instance used to write audit entries.

    Methods:
        log(action: str, status: str, start_time: float = None, metadata: dict = None, status_code: int = None):
            Logs a structured audit event with contextual metadata including user, role, request route,
            session ID, and timing info.

    Usage:
        logger = AuditLogger()
        logger.log(
            action="delete_variant",
            status="success",
            start_time=start_time,
            metadata={"variant_id": "123abc"},
            status_code=200
        )

    Example Output:
        {
            "timestamp": "2025-06-12T14:05:33.012Z",
            "level": "INFO",
            "user": "john_doe",
            "role": "admin",
            "ip": "192.168.1.12",
            "route": "admin_bp.delete_variant",
            "session_id": "abcd1234",
            "call_type": "admin_action",
            "action": "delete_variant",
            "status": "success",
            "status_code": 200,
            "duration_ms": 342.67,
            "extra": {
                "variant_id": "123abc"
            }
        }
    """

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
