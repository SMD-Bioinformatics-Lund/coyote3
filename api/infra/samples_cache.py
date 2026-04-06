"""Helpers for sample-home cache versioning and invalidation."""

from __future__ import annotations

import uuid

SAMPLES_CACHE_VERSION_KEY = "samples:list:version"
SAMPLES_CACHE_VERSION_TIMEOUT_SECONDS = 60 * 60 * 24 * 30


def samples_cache_version(app_obj) -> str:
    """Return active sample-home cache version token."""
    cache = getattr(app_obj, "cache", None)
    logger = getattr(app_obj, "logger", None)
    if cache is None:
        return "nocache"

    try:
        token = cache.get(SAMPLES_CACHE_VERSION_KEY)
        if token:
            return str(token)
        token = uuid.uuid4().hex
        cache.set(
            SAMPLES_CACHE_VERSION_KEY,
            token,
            timeout=SAMPLES_CACHE_VERSION_TIMEOUT_SECONDS,
        )
        return token
    except Exception as exc:  # pragma: no cover - defensive fallback
        if logger is not None:
            logger.warning("samples_cache_version_read_failed error=%s", exc)
        return "nocache"


def invalidate_samples_cache(adapter) -> None:
    """Bump the sample-home cache version token after sample changes."""
    app_obj = getattr(adapter, "app", None)
    cache = getattr(app_obj, "cache", None)
    logger = getattr(app_obj, "logger", None)
    if cache is None:
        return
    try:
        cache.set(
            SAMPLES_CACHE_VERSION_KEY,
            uuid.uuid4().hex,
            timeout=SAMPLES_CACHE_VERSION_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        if logger is not None:
            logger.warning("samples_cache_version_bump_failed error=%s", exc)
