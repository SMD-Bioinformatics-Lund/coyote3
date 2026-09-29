"""Durable retry storage for sanitized audit events during MongoDB outages."""

import logging
import os
import tempfile
from itertools import islice
from pathlib import Path
from typing import Any

from bson import json_util
from bson.errors import BSONError
from pymongo.errors import PyMongoError


class AuditSpool:
    """Store pending events on a persistent volume shared by API and worker processes."""

    def __init__(self, directory: Path) -> None:
        """Configure the directory without creating files until an event needs storage.

        Args:
            directory: Environment-specific path on the persistent logs mount.
        """
        self.directory = directory

    def persist(self, document: dict[str, Any]) -> None:
        """Atomically persist one event with its original MongoDB identity.

        Args:
            document: Sanitized event with an ObjectId in _id.

        Raises:
            OSError: The volume cannot durably accept the event.
        """
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary = tempfile.mkstemp(dir=self.directory, suffix=".pending")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(json_util.dumps(document))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.directory / f"{document['_id']}.json")
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def replay(self, collection: Any, *, limit: int = 100) -> int:
        """Replay a bounded batch and remove files only after acknowledged MongoDB writes.

        Args:
            collection: The original environment's audit collection.
            limit: Maximum number of files attempted in this batch.

        Returns:
            Number of acknowledged events. Concurrent replay is idempotent by _id.

        Raises:
            OSError: A pending file cannot be read or removed.

        Notes:
            Invalid files are retained with a .invalid suffix and a critical log,
            so one damaged record does not block delivery of valid events.
        """
        delivered = 0
        for path in islice(self.directory.glob("*.json"), max(0, limit)):
            try:
                document = json_util.loads(path.read_text(encoding="utf-8"))
                if not isinstance(document, dict) or str(document.get("_id")) != path.stem:
                    raise ValueError("Audit spool identity does not match its filename")
            except FileNotFoundError:
                continue
            except (ValueError, TypeError, KeyError, BSONError, OverflowError):
                try:
                    path.replace(path.with_suffix(".invalid"))
                except FileNotFoundError:
                    continue
                logging.getLogger("coyote3.audit").critical(
                    "Invalid audit spool file retained for operator recovery",
                    extra={"file": path.name},
                )
                continue
            try:
                result = collection.update_one(
                    {"_id": document["_id"]}, {"$setOnInsert": document}, upsert=True
                )
                if not result.acknowledged:
                    break
            except PyMongoError:
                break
            path.unlink(missing_ok=True)
            delivered += 1
        return delivered
