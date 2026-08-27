"""JSON logging and request-context helpers used by API and workers."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Structured request metadata attached to log records."""

    request_id: str
    client_ip: str | None
    method: str
    path: str
    user_agent: str | None = None


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "coyote3_request_context", default=None
)


def current_request_context() -> RequestContext | None:
    """Return the active request context, if one is bound."""
    return _request_context.get()


def bind_request_context(context: RequestContext) -> Token:
    """Bind request metadata for subsequent logs in this context."""
    return _request_context.set(context)


def reset_request_context(token: Token) -> None:
    """Reset a previously bound request context."""
    _request_context.reset(token)


class JsonFormatter(logging.Formatter):
    """One JSON object per line."""

    _standard_fields = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        context = current_request_context()
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "severity": record.levelname.lower(),
            "logger": record.name,
            "service": getattr(record, "service", None),
            "message": record.getMessage(),
        }
        if context is not None:
            payload.update(
                {
                    "request_id": context.request_id,
                    "client_ip": context.client_ip,
                    "method": context.method,
                    "path": context.path,
                }
            )
        for key, value in record.__dict__.items():
            if key not in self._standard_fields and key not in payload and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class ServiceFilter(logging.Filter):
    """Attach a service name to every record passing through a handler."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service_name
        return True


def configure_json_logging(
    *,
    service_name: str,
    level: str = "INFO",
    log_root: str | Path | None = None,
    file_enabled: bool = False,
    retention_days: int = 30,
    filename_prefix: str = "coyote3",
) -> None:
    """Configure root JSON logging for container stdout and optional files."""
    root = logging.getLogger()
    root.setLevel(str(level or "INFO").upper())
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    formatter = JsonFormatter()
    service_filter = ServiceFilter(service_name)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(service_filter)
    root.addHandler(console)

    if not file_enabled or not log_root:
        return
    try:
        Path(log_root).mkdir(parents=True, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            filename=str(Path(log_root) / f"{filename_prefix}-{service_name}.json.log"),
            when="midnight",
            interval=1,
            backupCount=max(int(retention_days), 1),
            encoding="utf-8",
            utc=True,
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(service_filter)
        root.addHandler(file_handler)
    except OSError:
        root.exception(
            "File logging could not be initialized; continuing with stdout",
            extra={"log_root": str(log_root)},
        )


def request_context_from_request(request: Any) -> RequestContext:
    """Build a request context from a Starlette/FastAPI request-like object."""
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").strip()
    client_ip = forwarded_for.split(",", 1)[0].strip() if forwarded_for else None
    if not client_ip and getattr(request, "client", None):
        client_ip = request.client.host
    return RequestContext(
        request_id=(request.headers.get("X-Request-ID") or "").strip() or str(uuid.uuid4()),
        client_ip=client_ip,
        method=request.method,
        path=request.url.path,
        user_agent=request.headers.get("User-Agent"),
    )


def elapsed_ms(started: float) -> float:
    """Return elapsed milliseconds from a perf-counter start value."""
    return round((time.perf_counter() - started) * 1000.0, 2)
