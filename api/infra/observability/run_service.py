"""Capture service output and startup failures before application logging exists."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import sys
from datetime import datetime

from api.infra.observability.logging import DailyServiceFileHandler, JsonFormatter


def output_record(line: str, service: str) -> logging.LogRecord:
    """Preserve structured records and classify plain startup/traceback output."""
    try:
        event = json.loads(line)
    except ValueError:
        event = None
    if isinstance(event, dict) and "message" in event:
        level = getattr(logging, str(event.get("severity", "info")).upper(), logging.INFO)
        record = logging.LogRecord(
            str(event.get("logger") or service), level, "", 0, str(event["message"]), (), None
        )
        for key, value in event.items():
            if key not in {"message", "severity", "logger", "timestamp"}:
                setattr(record, key, value)
        record.service = "ui" if event.get("logger") == "coyote.ui" else service
        if event.get("timestamp"):
            try:
                record.created = datetime.fromisoformat(str(event["timestamp"])).timestamp()
            except ValueError:
                pass
        return record
    level = (
        logging.ERROR if re.search(r"\b(ERROR|CRITICAL|FATAL|Traceback)\b", line) else logging.INFO
    )
    record = logging.LogRecord(service, level, "", 0, line, (), None)
    record.service = service
    return record


def main() -> int:
    """Run a service with inherited environment, forwarding shutdown and exit status."""
    service, *command = sys.argv[1:]
    handler = DailyServiceFileHandler(
        os.getenv("LOG_ROOT", "logs"), os.getenv("LOCAL_TIME_ZONE", "UTC")
    )
    handler.setFormatter(JsonFormatter())
    file_enabled = os.getenv("LOG_FILE_ENABLED", "1") == "1"
    environment = {**os.environ, "LOG_FILE_ENABLED": "0", "LOG_SERVICE_NAME": service}
    stopping = False
    try:
        child = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
    except OSError as exc:
        message = f"ERROR: Could not start {service}: {exc}"
        logging.getLogger(__name__).error(message)
        if file_enabled:
            handler.handle(output_record(message, service))
        return 1

    def forward_signal(signum, _frame) -> None:
        """Let the service perform its own graceful shutdown."""
        nonlocal stopping
        stopping = True
        child.send_signal(signum)

    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, forward_signal)
    for line in child.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        if file_enabled:
            handler.handle(output_record(line.rstrip("\n"), service))
    code = child.wait()
    if code and not stopping and file_enabled:
        handler.handle(output_record(f"ERROR: {service} exited with status {code}", service))
    return code if code >= 0 else 128 - code


if __name__ == "__main__":
    raise SystemExit(main())
