"""Cache backend behavior tests."""

from __future__ import annotations

import logging

import pytest

from cache_backend import DisabledCacheBackend, RedisCacheBackend, create_cache_backend


class _FakeRedis:
    """Provide  FakeRedis behavior."""

    def __init__(self):
        """Handle __init__."""
        self._values: dict[str, bytes] = {}

    def ping(self) -> bool:
        """Handle ping.

        Returns:
            bool: The function result.
        """
        return True

    def get(self, key: str):
        """Handle get.

        Args:
            key (str): Value for ``key``.

        Returns:
            The function result.
        """
        return self._values.get(key)

    def set(self, key: str, value: bytes):
        """Handle set.

        Args:
            key (str): Value for ``key``.
            value (bytes): Value for ``value``.

        Returns:
            The function result.
        """
        self._values[key] = value
        return True

    def setex(self, key: str, _ttl: int, value: bytes):
        """Handle setex.

        Args:
            key (str): Value for ``key``.
            _ttl (int): Value for ``_ttl``.
            value (bytes): Value for ``value``.

        Returns:
            The function result.
        """
        self._values[key] = value
        return True


def test_cache_backend_disabled_by_config():
    """Handle test cache backend disabled by config.

    Returns:
        The function result.
    """
    backend = create_cache_backend(
        config={"CACHE_ENABLED": False},
        logger=logging.getLogger("test.cache"),
        namespace="api",
    )
    assert isinstance(backend, DisabledCacheBackend)
    assert backend.get("k") is None
    assert backend.set("k", "v") is False


def test_cache_backend_falls_back_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch):
    """Handle test cache backend falls back when redis unavailable.

    Args:
        monkeypatch (pytest.MonkeyPatch): Value for ``monkeypatch``.

    Returns:
        The function result.
    """

    class _NoRedis:
        """Provide  NoRedis behavior."""

        @staticmethod
        def from_url(*args, **kwargs):  # noqa: ARG004
            """Handle from url.

            Args:
                *args: Additional positional values for ``args``.
                **kwargs: Additional keyword values for ``kwargs``.

            Returns:
                The function result.
            """
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
    """Handle test cache backend required raises when redis unavailable.

    Args:
        monkeypatch (pytest.MonkeyPatch): Value for ``monkeypatch``.

    Returns:
        The function result.
    """

    class _NoRedis:
        """Provide  NoRedis behavior."""

        @staticmethod
        def from_url(*args, **kwargs):  # noqa: ARG004
            """Handle from url.

            Args:
                *args: Additional positional values for ``args``.
                **kwargs: Additional keyword values for ``kwargs``.

            Returns:
                The function result.
            """
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
    """Handle test redis cache backend roundtrip.

    Args:
        monkeypatch (pytest.MonkeyPatch): Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    fake = _FakeRedis()

    class _RedisFactory:
        """Provide  RedisFactory behavior."""

        @staticmethod
        def from_url(*args, **kwargs):  # noqa: ARG004
            """Handle from url.

            Args:
                *args: Additional positional values for ``args``.
                **kwargs: Additional keyword values for ``kwargs``.

            Returns:
                The function result.
            """
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
