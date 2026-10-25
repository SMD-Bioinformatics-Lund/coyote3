"""Cache backend behavior tests."""

from __future__ import annotations

import logging
from datetime import datetime

import pytest
from bson import ObjectId

from api.infra.cache import DisabledCacheBackend, RedisCacheBackend, create_cache_backend


class _FakeRedis:
    """Provide  FakeRedis behavior."""

    def __init__(self):
        """__init__."""
        self._values: dict[str, bytes] = {}

    def ping(self) -> bool:
        """Ping."""
        return True

    def get(self, key: str):
        """Get."""
        return self._values.get(key)

    def set(self, key: str, value: bytes):
        """Set."""
        self._values[key] = value
        return True

    def setex(self, key: str, _ttl: int, value: bytes):
        """Setex."""
        self._values[key] = value
        return True

    def eval(self, _script: str, _key_count: int, key: str, ttl: int):
        """Emulate the atomic fixed-window counter result."""
        count = int(self._values.get(key, b"0")) + 1
        self._values[key] = str(count).encode()
        return [count, ttl]


def test_cache_backend_degrades_when_not_required_and_url_is_missing():
    """An explicitly non-required cache degrades to a no-op when unavailable."""
    backend = create_cache_backend(
        config={"CACHE_REQUIRED": "0"},
        logger=logging.getLogger("test.cache"),
        namespace="api",
    )
    assert isinstance(backend, DisabledCacheBackend)
    assert backend.get("k") is None
    assert backend.set("k", "v") is False


def test_cache_backend_falls_back_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch):

    class _NoRedis:
        """Provide  NoRedis behavior."""

        @staticmethod
        def from_url(*args, **kwargs):  # noqa: ARG004
            """From url."""
            raise RuntimeError("boom")

    monkeypatch.setattr("api.infra.cache.redis.Redis", _NoRedis)
    backend = create_cache_backend(
        config={
            "CACHE_REQUIRED": False,
            "CACHE_REDIS_URL": "redis://cache:6379/0",
        },
        logger=logging.getLogger("test.cache"),
        namespace="api",
    )
    assert isinstance(backend, DisabledCacheBackend)


def test_cache_backend_required_raises_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch):

    class _NoRedis:
        """Provide  NoRedis behavior."""

        @staticmethod
        def from_url(*args, **kwargs):  # noqa: ARG004
            """From url."""
            raise RuntimeError("boom")

    monkeypatch.setattr("api.infra.cache.redis.Redis", _NoRedis)
    with pytest.raises(RuntimeError):
        create_cache_backend(
            config={
                "CACHE_REQUIRED": True,
                "CACHE_REDIS_URL": "redis://cache:6379/0",
            },
            logger=logging.getLogger("test.cache"),
            namespace="api",
        )


def test_redis_cache_backend_roundtrip(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeRedis()

    class _RedisFactory:
        """Provide  RedisFactory behavior."""

        @staticmethod
        def from_url(*args, **kwargs):  # noqa: ARG004
            """From url."""
            return fake

    monkeypatch.setattr("api.infra.cache.redis.Redis", _RedisFactory)

    backend = create_cache_backend(
        config={
            "CACHE_REQUIRED": True,
            "CACHE_REDIS_URL": "redis://cache:6379/0",
            "CACHE_KEY_PREFIX": "coyote3_cache",
            "CACHE_DEFAULT_TIMEOUT": 60,
        },
        logger=logging.getLogger("test.cache"),
        namespace="web",
    )

    assert isinstance(backend, RedisCacheBackend)
    assert backend.get("sample-key") is None
    assert backend.set("sample-key", {"k": 1}, timeout=10) is True
    assert backend.get("sample-key") == {"k": 1}
    assert backend.increment_window("quota", window_seconds=30) == (1, 30)
    assert backend.increment_window("quota", window_seconds=30) == (2, 30)


def test_disabled_cache_rejects_distributed_counters():
    """Rate limiting must fail closed when no distributed backend exists."""
    with pytest.raises(RuntimeError, match="Redis is required"):
        DisabledCacheBackend().increment_window("quota", window_seconds=60)


def test_cache_extended_json_preserves_mongo_values_and_rejects_pickle():
    fake = _FakeRedis()
    backend = RedisCacheBackend(
        client=fake, key_prefix="test", default_timeout=60, logger=logging.getLogger("test.cache")
    )
    value = {
        "_id": ObjectId(),
        "created": datetime(2026, 1, 1),
        "missing": None,
        "items": [0, False, "text"],
    }
    assert backend.set("document", value)
    assert backend.get("document") == value
    assert fake._values["test:document"].startswith(b"{")
    fake._values["test:old"] = b"\x80\x04N."
    assert backend.get("old") is None
    fake._values["test:broken"] = b"{invalid"
    assert backend.get("broken") is None


def test_cache_connection_logs_do_not_expose_credentials(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise RuntimeError("redis://:private-password@cache:6379/0")

    monkeypatch.setattr("api.infra.cache.redis.Redis.from_url", fail)
    with caplog.at_level(logging.WARNING):
        create_cache_backend(
            config={
                "CACHE_REQUIRED": False,
                "CACHE_REDIS_URL": "redis://:private-password@cache:6379/0",
            },
            logger=logging.getLogger("test.cache"),
            namespace="test",
        )
    assert "private-password" not in caplog.text
    assert "RuntimeError" in caplog.text
