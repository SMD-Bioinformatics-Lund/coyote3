"""Durable disk-log error delivery, independent of Celery and the API runtime."""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def write_json(path: Path, value: Any) -> None:
    """Atomically replace monitoring state on the same filesystem."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(path)


class DiskErrorMonitor:
    """Queue error batches with log snapshots and retry unsent group deliveries."""

    def __init__(self, log_root: Path) -> None:
        """Load scan offsets and pending deliveries from the persistent log volume."""
        self.root = log_root
        self.spool = log_root / ".error-mail"
        self.spool.mkdir(parents=True, exist_ok=True)
        self.state_path = self.spool / "offsets.json"
        self.offsets = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}

    def scan(self) -> None:
        """Snapshot new ERROR/CRITICAL records, committing jobs before advancing offsets."""
        for path in sorted(self.root.glob("[0-9][0-9][0-9][0-9]/*/*/*.log*")):
            compressed = path.suffix == ".gz"
            logical_path = path.with_suffix("") if compressed else path
            key = str(logical_path.relative_to(self.root))
            start = self.offsets.get(key, 0)
            if not compressed and path.stat().st_size < start:
                start = 0
            errors = []
            opener = gzip.open if compressed else open
            with opener(path, "rb") as source:
                source.seek(start)
                end = start
                for _ in range(10000):
                    line = source.readline()
                    if not line or not line.endswith(b"\n"):
                        break
                    end = source.tell()
                    try:
                        record = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if isinstance(record, dict) and record.get("severity") in {"error", "critical"}:
                        errors.append(record)
            if end == start:
                continue
            if errors:
                job_id = hashlib.sha256(f"{key}:{start}:{end}".encode()).hexdigest()
                job_path = self.spool / f"{job_id}.json"
                snapshot = self.spool / f"{job_id}.gz"
                if not job_path.exists():
                    with opener(path, "rb") as source, gzip.open(snapshot, "wb") as target:
                        shutil.copyfileobj(source, target)
                    write_json(job_path, {"source": key, "errors": errors, "sent": []})
            self.offsets[key] = end
            write_json(self.state_path, self.offsets)

    def deliver(
        self, recipients: list[str], sender: Callable[..., bool], *, limit: int = 10
    ) -> int:
        """Retry queued messages for current recipients, tracking individual acceptance.

        Args:
            recipients: Current active group email addresses; empty leaves jobs pending.
            sender: SMTP callback accepting message details and attachment bytes.
            limit: Maximum error batches attempted in this pass.

        Returns:
            Number of batches accepted for every current recipient. A crash between
            SMTP acceptance and state persistence can cause duplicate delivery.
        """
        recipients = sorted(set(address.strip() for address in recipients if address.strip()))
        if not recipients:
            return 0
        completed = 0
        jobs = [path for path in sorted(self.spool.glob("*.json")) if path != self.state_path]
        for path in jobs[:limit]:
            job = json.loads(path.read_text())
            snapshot = path.with_suffix(".gz")
            source = Path(job["source"])
            body = f"Log file: {job['source']}\n\n" + "\n\n".join(
                f"{event.get('timestamp', '')} {event.get('message', '')}\n{event.get('exception', '')}"
                for event in job["errors"]
            )
            for address in recipients:
                if address in job["sent"]:
                    continue
                if sender(
                    to_email=address,
                    subject=f"Coyote3 system error: {source.name}",
                    text_body=body,
                    severity="error",
                    purpose="security",
                    attachments=[(source.name + ".gz", snapshot.read_bytes())],
                ):
                    job["sent"].append(address)
                    write_json(path, job)
            if set(recipients).issubset(job["sent"]):
                path.unlink()
                snapshot.unlink(missing_ok=True)
                completed += 1
        return completed


def parse_syslog(message: str) -> logging.LogRecord | None:
    """Translate internal Nginx/Vite syslog datagrams to service log records."""
    match = re.match(r"^<(\d+)>.*?\b(ui|proxy|docs|redis):\s*(.*)$", message, re.DOTALL)
    if not match:
        return None
    priority, service, content = match.groups()
    severity = int(priority) % 8
    if re.search(r'"\s+5\d\d\s', content):
        severity = 3
    level = logging.ERROR if severity <= 3 else logging.WARNING if severity == 4 else logging.INFO
    record = logging.LogRecord(f"coyote.{service}", level, "", 0, content, (), None)
    record.service = service
    return record
