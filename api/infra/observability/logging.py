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
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


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
        """Serialize a record with request context and nonprivate extra fields.

        Args:
            record: Log event to format, including optional exception information.

        Returns:
            JSON object text with a UTC timestamp. Values unsupported by JSON are
            stringified; extra fields cannot overwrite standard payload fields.
        """
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
        """Set the service label attached to subsequent log records.

        Args:
            service_name: Label identifying the emitting runtime service.
        """
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach the configured service label without rejecting the record.

        Args:
            record: Log event whose ``service`` attribute is overwritten.

        Returns:
            Always ``True`` so the handler retains the event.
        """
        record.service = "ui" if record.name == "coyote.ui" else self.service_name
        return True


class DailyServiceFileHandler(logging.Handler):
    """Append service logs by local calendar date without cross-process renames."""

    def __init__(self, log_root: str | Path, timezone_name: str = "UTC") -> None:
        """Set the log directory and IANA timezone used for midnight boundaries."""
        super().__init__()
        self.log_root = Path(log_root)
        self.timezone = ZoneInfo(timezone_name)

    def emit(self, record: logging.LogRecord) -> None:
        """Append a record, reopening the file so retention cannot leave stale handles."""
        try:
            day = datetime.fromtimestamp(record.created, self.timezone)
            service = getattr(record, "service", "api")
            if service not in {"api", "worker", "beat", "ui", "proxy", "docs", "monitor", "redis"}:
                service = "api"
            directory = self.log_root / day.strftime("%Y/%m/%d")
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{service}_{day:%Y-%m-%d}.log"
            with path.open("a", encoding="utf-8") as stream:
                stream.write(self.format(record) + "\n")
        except Exception:
            self.handleError(record)


def configure_json_logging(
    *,
    service_name: str,
    level: str = "INFO",
    log_root: str | Path | None = None,
    file_enabled: bool = False,
    retention_days: int = 30,
    filename_prefix: str = "coyote3",
    timezone_name: str = "UTC",
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
        file_handler = DailyServiceFileHandler(log_root, timezone_name)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(service_filter)
        root.addHandler(file_handler)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "celery", "celery.task"):
            logger = logging.getLogger(name)
            logger.handlers.clear()
            logger.propagate = True
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
