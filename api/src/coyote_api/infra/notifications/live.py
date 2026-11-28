# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Share committed MongoDB changes among this API process's authenticated inbox streams."""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from threading import Event, Thread
from typing import Any

from coyote.application.notifications.activity import ActivityNotificationService
from pymongo.change_stream import CollectionChangeStream

logger = logging.getLogger(__name__)


class NotificationFeed:
    """Own one collection watcher per source, independent of the number of browser tabs."""

    def __init__(self) -> None:
        self._listeners: dict[asyncio.Queue[None], str] = {}
        self._stop = Event()
        self._threads: list[Thread] = []

    def _signal(self, recipients: set[str] | None) -> None:
        """Coalesce unread signals; the inbox endpoint enforces current access on each read."""
        for queue, username in self._listeners.items():
            if (recipients is None or username in recipients) and queue.empty():
                queue.put_nowait(None)

    def _watch(
        self,
        source: str,
        open_cursor: Callable[[], CollectionChangeStream[dict[str, Any]]],
        service: ActivityNotificationService,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Consume committed changes. Scheduled delivery reconciles gaps after outages."""
        delay = 1
        while not self._stop.is_set():
            try:
                with open_cursor() as cursor:
                    if source == "inbox":
                        loop.call_soon_threadsafe(self._signal, None)
                    while cursor.alive and not self._stop.is_set():
                        change = cursor.try_next()
                        delay = 1
                        if change is None:
                            continue
                        if source == "inbox":
                            recipients = (
                                None
                                if change.get("audience") == "all"
                                else set(change.get("recipients") or [])
                            )
                            loop.call_soon_threadsafe(self._signal, recipients)
                        else:
                            document = change["document"]
                            if source == "release":
                                document = service.activity.release_event(document)
                            service.deliver_event(document)
            except Exception as exc:
                logger.warning(
                    "Notification watcher %s interrupted (%s)", source, type(exc).__name__
                )
            self._stop.wait(delay)
            delay = min(30, delay * 2)

    async def events(
        self,
        username: str,
        service_factory: Callable[[], ActivityNotificationService],
    ) -> AsyncIterator[str]:
        """Send content-free refresh signals. Reconnect periodically to recheck authentication."""
        loop = asyncio.get_running_loop()
        if not self._threads:
            service = service_factory()
            for name, open_cursor in service.activity.live_sources(service.environment).items():
                thread = Thread(
                    target=self._watch,
                    args=(name, open_cursor, service, loop),
                    name=f"notification-{name}",
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)
        queue: asyncio.Queue[None] = asyncio.Queue(maxsize=1)
        self._listeners[queue] = username.strip().lower()
        deadline = loop.time() + 120
        try:
            yield "retry: 1000\nevent: ready\ndata: {}\n\n"
            while (remaining := deadline - loop.time()) > 0 and not self._stop.is_set():
                try:
                    await asyncio.wait_for(queue.get(), timeout=min(15, remaining))
                except TimeoutError:
                    yield ": heartbeat\n\n"
                else:
                    yield "event: changed\ndata: {}\n\n"
        finally:
            self._listeners.pop(queue, None)

    async def close(self) -> None:
        """Finish outstanding reads before the runtime closes its MongoDB clients."""
        self._stop.set()
        self._signal(None)
        await asyncio.gather(*(asyncio.to_thread(thread.join) for thread in self._threads))
