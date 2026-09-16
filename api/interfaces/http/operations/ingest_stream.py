"""Stream one synchronous ingest operation's logs and terminal response."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from contextvars import copy_context
from datetime import datetime, timezone
from queue import Empty, Full, Queue
from threading import Event, Thread
from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse


def stream_ingest(operation: Callable[[], Any]) -> StreamingResponse:
    """Send request-local log events followed by exactly one result or error.

    Only ingest loggers on the operation's thread are captured. Disconnecting
    stops log delivery, not database work; clients must not assume rollback.
    The bounded buffer drops excess log lines rather than blocking ingestion.
    Errors after response headers use an error event with the original status.
    """

    def events() -> Iterator[str]:
        """Run the operation while yielding newline-delimited JSON events."""
        queue: Queue[dict[str, Any]] = Queue(maxsize=256)
        disconnected = Event()

        class RequestLogs(logging.Handler):
            """Capture only messages emitted by this ingest thread."""

            def emit(self, record: logging.LogRecord) -> None:
                """Offer a formatted log without stalling database processing."""
                if record.thread != worker.ident or disconnected.is_set():
                    return
                try:
                    queue.put_nowait(
                        {
                            "event": "log",
                            "timestamp": datetime.fromtimestamp(
                                record.created, timezone.utc
                            ).isoformat(),
                            "level": record.levelname,
                            "logger": record.name,
                            "message": record.getMessage(),
                        }
                    )
                except Full:
                    pass

        def run() -> None:
            """Keep logging and response capture scoped to this invocation."""
            handler = RequestLogs()
            loggers = [
                logging.getLogger("api.application.ingest"),
                logging.getLogger("api.interfaces.http.operations.internal"),
            ]
            for logger in loggers:
                logger.addHandler(handler)
            try:
                result = operation()
                if isinstance(result, JSONResponse):
                    terminal = {
                        "event": "error" if result.status_code >= 400 else "result",
                        "status_code": result.status_code,
                        "data": json.loads(result.body),
                    }
                else:
                    terminal = {"event": "result", "data": result}
            except HTTPException as exc:
                terminal = {
                    "event": "error",
                    "status_code": exc.status_code,
                    "data": {"detail": exc.detail},
                }
            except Exception as exc:
                logging.getLogger("api.application.ingest").exception("Ingest stream failed")
                terminal = {
                    "event": "error",
                    "status_code": 500,
                    "data": {"error": f"{type(exc).__name__}: {exc}"},
                }
            finally:
                for logger in loggers:
                    logger.removeHandler(handler)
                handler.close()
            while not disconnected.is_set():
                try:
                    queue.put(terminal, timeout=0.5)
                    break
                except Full:
                    continue

        context = copy_context()
        worker = Thread(target=lambda: context.run(run), name="ingest-stream", daemon=True)
        worker.start()
        try:
            while True:
                try:
                    event = queue.get(timeout=10)
                except Empty:
                    event = {"event": "heartbeat"}
                yield json.dumps(event) + "\n"
                if event["event"] in {"result", "error"}:
                    break
        finally:
            disconnected.set()

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
