"""Durable disk-log error delivery, independent of Celery and the API runtime."""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
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
        self._completed: dict[str, tuple[int, int, int, int]] = {}

    def scan(self) -> None:
        """Scan new records, attaching only the scanned batch to queued errors.

        Unchanged files already read to EOF are skipped before opening them, so
        archived gzip logs are not decompressed on every polling cycle. File
        size, timestamps and inode changes invalidate that in-memory cache.
        Durable offsets still control recovery after a monitor restart.
        """
        for path in sorted(self.root.glob("[0-9][0-9][0-9][0-9]/*/*/*.log*")):
            stat = path.stat()
            signature = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            if self._completed.get(str(path)) == signature:
                continue
            compressed = path.suffix == ".gz"
            logical_path = path.with_suffix("") if compressed else path
            key = str(logical_path.relative_to(self.root))
            start = self.offsets.get(key, 0)
            if not compressed and path.stat().st_size < start:
                start = 0
            errors = []
            batch = []
            reached_end = False
            opener = gzip.open if compressed else open
            with opener(path, "rb") as source:
                source.seek(start)
                end = start
                for _ in range(10000):
                    line = source.readline()
                    if not line or not line.endswith(b"\n"):
                        reached_end = True
                        break
                    end = source.tell()
                    batch.append(line)
                    try:
                        record = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if isinstance(record, dict) and (
                        record.get("severity") in {"error", "critical"}
                        or (
                            record.get("severity") == "warning"
                            and record.get("event_type") == "ingest.expected_files_missing"
                        )
                    ):
                        errors.append(record)
            if end == start:
                if reached_end:
                    self._completed[str(path)] = signature
                continue
            if errors:
                job_id = hashlib.sha256(f"{key}:{start}:{end}".encode()).hexdigest()
                job_path = self.spool / f"{job_id}.json"
                snapshot = self.spool / f"{job_id}.excerpt"
                if not job_path.exists():
                    with snapshot.open("wb") as target:
                        target.writelines(batch)
                    write_json(
                        job_path,
                        {
                            "source": key,
                            "errors": errors,
                            "sent": [],
                            "start": start,
                            "end": end,
                            "snapshot_format": "plain",
                        },
                    )
            self.offsets[key] = end
            write_json(self.state_path, self.offsets)
            if reached_end:
                self._completed[str(path)] = signature

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
            plain_snapshot = job.get("snapshot_format") == "plain"
            snapshot = path.with_suffix(".excerpt" if plain_snapshot else ".gz")
            source = Path(job["source"])
            severity = (
                "error"
                if any(event.get("severity") in {"error", "critical"} for event in job["errors"])
                else "warning"
            )
            scope = (
                f"Attachment contains log bytes {job['start']}–{job['end']} (scanned batch).\n"
                if "start" in job
                else ""
            )
            body = f"Log file: {job['source']}\n{scope}\n" + "\n\n".join(
                f"{event.get('timestamp', '')} {event.get('message', '')}\n{event.get('exception', '')}"
                for event in job["errors"]
            )
            for address in recipients:
                if address in job["sent"]:
                    continue
                if sender(
                    to_email=address,
                    subject=f"Coyote3 system {severity}: {source.name}",
                    text_body=body,
                    severity=severity,
                    purpose="security",
                    attachments=[
                        (source.name + ("" if plain_snapshot else ".gz"), snapshot.read_bytes())
                    ],
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
