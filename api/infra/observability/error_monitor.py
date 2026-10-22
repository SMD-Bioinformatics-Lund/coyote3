"""Durable disk-log error delivery, independent of Celery and the API runtime."""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)
MAX_BATCH_BYTES = 1024 * 1024
MAX_MESSAGE_BYTES = 64 * 1024
MAX_ATTEMPTS = 20
MAX_SPOOL_BYTES = 256 * 1024 * 1024


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
        spool_bytes = sum(path.stat().st_size for path in self.spool.iterdir() if path.is_file())
        for path in sorted(self.root.glob("[0-9][0-9][0-9][0-9]/*/*/*.log*")):
            if spool_bytes + 3 * MAX_BATCH_BYTES > MAX_SPOOL_BYTES:
                logger.error(
                    "Error-mail spool capacity reached; scan offsets retained for recovery"
                )
                break
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
                    line = source.readline(MAX_BATCH_BYTES + 1)
                    if len(line) > MAX_BATCH_BYTES:
                        # Consume oversized records without retaining unbounded memory.
                        while line and not line.endswith(b"\n"):
                            line = source.readline(MAX_BATCH_BYTES)
                        if not line:
                            reached_end = True
                            break
                        end = source.tell()
                        errors.append(
                            {
                                "severity": "error",
                                "message": "Oversized log record omitted; inspect the source log.",
                            }
                        )
                        break
                    if not line or not line.endswith(b"\n"):
                        reached_end = True
                        break
                    if batch and end - start + len(line) > MAX_BATCH_BYTES:
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
                            "created_at": time.time(),
                        },
                    )
                    spool_bytes += job_path.stat().st_size + snapshot.stat().st_size
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
        now = time.time()
        jobs = []
        for path in self.spool.glob("*.json"):
            if path in {self.state_path, self.spool / "status.json"}:
                continue
            try:
                if path.stat().st_size > MAX_BATCH_BYTES * 2:
                    raise ValueError("Oversized delivery metadata")
                job = json.loads(path.read_text())
                if not isinstance(job.get("errors"), list) or not isinstance(job.get("sent"), list):
                    raise ValueError("Invalid delivery metadata")
                if not isinstance(job.get("source"), str):
                    raise ValueError("Invalid log source")
                due = float(job.get("next_attempt", 0))
                int(job.get("attempts", 0))
                if not all(isinstance(event, dict) for event in job["errors"]):
                    raise ValueError("Invalid event metadata")
                if due <= now:
                    jobs.append((due, path.name, path, job))
            except (ValueError, TypeError, AttributeError):
                path.rename(path.with_suffix(".quarantined"))
                logger.error("Quarantined invalid error-mail metadata: %s", path.name)
        for _, _, path, job in sorted(jobs)[: max(0, limit)]:
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
            body = body.encode("utf-8")[:MAX_MESSAGE_BYTES].decode("utf-8", errors="ignore")
            try:
                with snapshot.open("rb") as attachment:
                    content = attachment.read(MAX_BATCH_BYTES)
            except OSError:
                content = b"Log excerpt unavailable; inspect the retained source log.\n"
            for address in recipients:
                if address in job["sent"]:
                    continue
                try:
                    accepted = sender(
                        to_email=address,
                        subject=f"Coyote3 system {severity}: {source.name}",
                        text_body=body,
                        severity=severity,
                        purpose="security",
                        attachments=[(source.name + ("" if plain_snapshot else ".gz"), content)],
                    )
                except Exception:
                    logger.exception("Error-mail transport failed")
                    accepted = False
                if accepted:
                    job["sent"].append(address)
                    write_json(path, job)
            if set(recipients).issubset(job["sent"]):
                path.unlink()
                snapshot.unlink(missing_ok=True)
                completed += 1
            else:
                attempts = int(job.get("attempts", 0)) + 1
                job.update(
                    attempts=attempts,
                    last_attempt=now,
                    next_attempt=now + min(3600, 30 * 2 ** min(attempts - 1, 7)),
                    last_error="delivery_not_accepted",
                )
                write_json(path, job)
                if attempts >= MAX_ATTEMPTS:
                    path.rename(path.with_suffix(".quarantined"))
                    logger.error("Error-mail retries exhausted: %s", path.name)
        write_json(
            self.spool / "status.json",
            {
                "updated_at": now,
                "pending": sum(
                    1
                    for path in self.spool.glob("*.json")
                    if path.name not in {"offsets.json", "status.json"}
                ),
                "quarantined": sum(1 for _ in self.spool.glob("*.quarantined")),
                "oldest_pending_age_seconds": max(
                    (
                        max(0, int(now - path.stat().st_mtime))
                        for path in self.spool.glob("*.excerpt")
                    ),
                    default=0,
                ),
                "spool_bytes": sum(
                    path.stat().st_size for path in self.spool.iterdir() if path.is_file()
                ),
                "capacity_bytes": MAX_SPOOL_BYTES,
            },
        )
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
