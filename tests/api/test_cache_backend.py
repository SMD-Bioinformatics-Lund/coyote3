"""Cache backend behavior tests."""

from __future__ import annotations

import logging

import pytest

from cache_backend import DisabledCacheBackend, RedisCacheBackend, create_cache_backend


class _FakeRedis:
    def __init__(self):
        self._values: dict[str, bytes] = {}

    def ping(self) -> bool:
        return True

    def get(self, key: str):
        return self._values.get(key)

    def set(self, key: str, value: bytes):
        self._values[key] = value
        return True

    def setex(self, key: str, _ttl: int, value: bytes):
        self._values[key] = value
        return True


def test_cache_backend_disabled_by_config():
    backend = create_cache_backend(
        config={"CACHE_ENABLED": False},
        logger=logging.getLogger("test.cache"),
        namespace="api",
    )
    assert isinstance(backend, DisabledCacheBackend)
    assert backend.get("k") is None
    assert backend.set("k", "v") is False


def test_cache_backend_falls_back_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch):
    class _NoRedis:
        @staticmethod
        def from_url(*args, **kwargs):  # noqa: ARG004
            raise RuntimeError("boom")

    monkeypatch.setattr("cache_backend.redis.Redis", _NoRedis)
    backend = create_cache_backend(
        config={
            "CACHE_ENABLED": True,
            "CACHE_REQUIRED": False,
            "CACHE_REDIS_URL": "redis://cache:6379/0",
        },
        logger=logging.getLogger("test.cache"),
        namespace="api",
    )
    assert isinstance(backend, DisabledCacheBackend)


def test_cache_backend_required_raises_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch):
    class _NoRedis:
        @staticmethod
        def from_url(*args, **kwargs):  # noqa: ARG004
            raise RuntimeError("boom")

    monkeypatch.setattr("cache_backend.redis.Redis", _NoRedis)
    with pytest.raises(RuntimeError):
        create_cache_backend(
            config={
                "CACHE_ENABLED": True,
                "CACHE_REQUIRED": True,
                "CACHE_REDIS_URL": "redis://cache:6379/0",
            },
            logger=logging.getLogger("test.cache"),
            namespace="api",
        )


def test_redis_cache_backend_roundtrip(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeRedis()

    class _RedisFactory:
        @staticmethod
        def from_url(*args, **kwargs):  # noqa: ARG004
            return fake

    monkeypatch.setattr("cache_backend.redis.Redis", _RedisFactory)

    backend = create_cache_backend(
        config={
            "CACHE_ENABLED": True,
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
