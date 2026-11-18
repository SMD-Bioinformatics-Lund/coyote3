# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Standalone error-email monitor and internal syslog receiver."""

from __future__ import annotations

import logging
import socketserver
import threading
import time
from functools import partial
from pathlib import Path
from types import SimpleNamespace

from coyote_mongo.connections import MongoConnections
from coyote_mongo.repositories.users import UsersRepository

from coyote_api.config.runtime_settings import DefaultConfig
from coyote_api.infra.notifications.email import send_email
from coyote_api.infra.observability.error_monitor import DiskErrorMonitor, parse_syslog
from coyote_api.infra.observability.logging import (
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

    server = socketserver.UDPServer(
        (settings.COYOTE4_MONITOR_HOST, settings.COYOTE4_MONITOR_PORT),
        SyslogHandler,
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monitor = DiskErrorMonitor(root)
    from coyote_api.config.backend import BackendSettings

    connections = MongoConnections(BackendSettings.from_runtime(config).mongo.runtime_values())
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
