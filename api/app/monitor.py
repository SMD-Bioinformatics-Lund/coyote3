"""Standalone error-email monitor and internal syslog receiver."""

from __future__ import annotations

import logging
import socketserver
import threading
import time
from functools import partial
from pathlib import Path
from types import SimpleNamespace

from api.config.runtime_settings import DefaultConfig
from api.infra.mongo.connections import MongoConnections
from api.infra.mongo.repositories.users import UsersRepository
from api.infra.notifications.email import send_email
from api.infra.observability.error_monitor import DiskErrorMonitor, parse_syslog
from api.infra.observability.logging import (
    DailyServiceFileHandler,
    JsonFormatter,
    configure_json_logging,
)


def main() -> None:
    """Receive internal syslog and retry persisted emails without API, Redis, or Celery."""
    settings = DefaultConfig()
    config = {key: getattr(settings, key) for key in dir(settings) if key.isupper()}
    root = Path(settings.LOG_ROOT)
    configure_json_logging(
        service_name="monitor",
        log_root=root,
        file_enabled=True,
        timezone_name=settings.LOG_TIMEZONE,
    )
    handler = DailyServiceFileHandler(root, settings.LOG_TIMEZONE)
    handler.setFormatter(JsonFormatter())

    class SyslogHandler(socketserver.BaseRequestHandler):
        """Accept syslog only on the Compose network; no host port is published."""

        def handle(self) -> None:
            """Write one validated service datagram to its daily log."""
            record = parse_syslog(self.request[0].decode("utf-8", errors="replace"))
            if record is not None:
                handler.handle(record)

    server = socketserver.UDPServer(("0.0.0.0", 5514), SyslogHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monitor = DiskErrorMonitor(root)
    connections = MongoConnections(config)
    collection_name = settings.DB_COLLECTIONS_CONFIG["identity"]["users_collection"]
    users = UsersRepository(
        SimpleNamespace(users_collection=connections.databases["identity"][collection_name])
    )
    try:
        while True:
            try:
                monitor.scan()
                if not settings.ERROR_EMAIL_GROUP.strip():
                    raise ValueError("ERROR_EMAIL_GROUP must name a recipient role")
                recipients = users.list_active_users_for_notifications(
                    role_ids=[settings.ERROR_EMAIL_GROUP]
                )
                monitor.deliver(
                    [str(user.get("email") or "") for user in recipients],
                    partial(send_email, config=config),
                )
            except Exception:
                logging.getLogger(__name__).warning(
                    "Error email delivery pending; retrying", exc_info=True
                )
            time.sleep(5)
    finally:
        server.shutdown()
        connections.close()


if __name__ == "__main__":
    main()
