"""Unified Redis cache backend for API and UI runtimes."""

from __future__ import annotations

import logging
import pickle
from typing import Any

import redis


class DisabledCacheBackend:
    """No-op cache backend used when Redis is disabled/unavailable."""

    def __init__(self, reason: str = "disabled"):
        self.reason = reason

    def get(self, _key: str) -> Any | None:
        return None

    def set(self, _key: str, _value: Any, timeout: int | None = None) -> bool:  # noqa: ARG002
        return False


class RedisCacheBackend:
    """Redis-backed cache with pickle payload serialization."""

    def __init__(
        self,
        *,
        client: redis.Redis,
        key_prefix: str,
        default_timeout: int,
        logger: logging.Logger,
    ) -> None:
        self._client = client
        self._key_prefix = key_prefix.rstrip(":")
        self._default_timeout = int(default_timeout)
        self._logger = logger

    def _key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"

    def get(self, key: str) -> Any | None:
        cache_key = self._key(key)
        try:
            raw = self._client.get(cache_key)
        except Exception as exc:
            self._logger.warning("cache_get_error key=%s error=%s", cache_key, exc)
            return None

        if raw is None:
            self._logger.debug("cache_get_miss key=%s", cache_key)
            return None

        try:
            value = pickle.loads(raw)
        except Exception as exc:
            self._logger.warning("cache_deserialize_error key=%s error=%s", cache_key, exc)
            return None

        self._logger.debug("cache_get_hit key=%s", cache_key)
        return value

    def set(self, key: str, value: Any, timeout: int | None = None) -> bool:
        cache_key = self._key(key)
        ttl = self._default_timeout if timeout is None else int(timeout)

        try:
            payload = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
            if ttl > 0:
                self._client.setex(cache_key, ttl, payload)
            else:
                self._client.set(cache_key, payload)
        except Exception as exc:
            self._logger.warning("cache_set_error key=%s error=%s", cache_key, exc)
            return False

        self._logger.debug("cache_set key=%s ttl=%s", cache_key, ttl)
        return True


def create_cache_backend(
    *,
    config: dict[str, Any],
    logger: logging.Logger,
    namespace: str,
) -> RedisCacheBackend | DisabledCacheBackend:
    """Create a cache backend from runtime config."""
    cache_enabled = bool(config.get("CACHE_ENABLED", True))
    if not cache_enabled:
        logger.info("cache_backend_disabled namespace=%s reason=config_disabled", namespace)
        return DisabledCacheBackend(reason="config_disabled")

    redis_url = str(config.get("CACHE_REDIS_URL") or "").strip()
    if not redis_url:
        cache_required = bool(config.get("CACHE_REQUIRED", False))
        msg = f"cache_backend_unavailable namespace={namespace} reason=missing_url"
        if cache_required:
            raise RuntimeError(msg)
        logger.warning("%s", msg)
        return DisabledCacheBackend(reason="missing_url")

    cache_required = bool(config.get("CACHE_REQUIRED", False))
    socket_connect_timeout = float(config.get("CACHE_REDIS_CONNECT_TIMEOUT", 1.0))
    socket_timeout = float(config.get("CACHE_REDIS_SOCKET_TIMEOUT", 1.0))
    key_prefix = str(config.get("CACHE_KEY_PREFIX", "coyote3_cache"))
    default_timeout = int(config.get("CACHE_DEFAULT_TIMEOUT", 300))
    full_prefix = f"{key_prefix}:{namespace}"

    try:
        client = redis.Redis.from_url(
            redis_url,
            decode_responses=False,
            socket_connect_timeout=socket_connect_timeout,
            socket_timeout=socket_timeout,
            health_check_interval=30,
        )
        client.ping()
    except Exception as exc:
        if cache_required:
            raise RuntimeError(
                f"cache_backend_unavailable namespace={namespace} redis_url={redis_url}"
            ) from exc
        logger.warning(
            "cache_backend_unavailable namespace=%s redis_url=%s error=%s",
            namespace,
            redis_url,
            exc,
        )
        return DisabledCacheBackend(reason="unreachable")

    logger.info("cache_backend_ready namespace=%s redis_url=%s", namespace, redis_url)
    return RedisCacheBackend(
        client=client,
        key_prefix=full_prefix,
        default_timeout=default_timeout,
        logger=logger,
    )
