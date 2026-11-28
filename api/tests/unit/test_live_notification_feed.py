"""Exercise browser fan-out and watcher shutdown with a synthetic change cursor."""

import asyncio
from contextlib import contextmanager
from queue import Empty, Queue
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote_api.infra.notifications.live import NotificationFeed


@pytest.mark.asyncio
async def test_selected_and_broadcast_changes_wake_only_their_addressed_browsers():
    feed = NotificationFeed()
    changes = Queue()
    connected = Event()
    closed = Event()

    class Cursor:
        alive = True

        def try_next(self):
            try:
                return changes.get(timeout=0.05)
            except Empty:
                return None

    @contextmanager
    def watch():
        assert connected.wait(2)
        try:
            yield Cursor()
        finally:
            closed.set()

    factory = Mock(
        return_value=SimpleNamespace(
            environment="staging",
            activity=Mock(live_sources=Mock(return_value={"inbox": watch})),
        )
    )
    alice = feed.events("Alice", factory)
    bob = feed.events("bob", factory)

    async def receive(stream):
        return await asyncio.wait_for(anext(stream), 2)

    try:
        assert "event: ready" in await receive(alice)
        assert "event: ready" in await receive(bob)
        factory.assert_called_once()
        connected.set()
        await asyncio.gather(receive(alice), receive(bob))  # Watch subscription catch-up.
        waiting_bob = asyncio.create_task(receive(bob))
        changes.put({"audience": "selected", "recipients": ["alice"], "title": "Private text"})
        assert await receive(alice) == "event: changed\ndata: {}\n\n"
        assert not waiting_bob.done()
        changes.put({"audience": "all"})
        assert await waiting_bob == "event: changed\ndata: {}\n\n"
        assert "changed" in await receive(alice)
    finally:
        await feed.close()
        await alice.aclose()
        await bob.aclose()
    assert closed.is_set()
