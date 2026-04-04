"""Security repository wiring helpers."""

from __future__ import annotations

from functools import lru_cache

from api.extensions import store
from api.security.ports import SecurityRepository

_override_repository: SecurityRepository | None = None


def set_security_repository(repository: SecurityRepository) -> None:
    """Override the default security repository implementation.

    Args:
        repository: Repository implementation to use for subsequent lookups.

    Returns:
        ``None``.
    """
    global _override_repository
    _override_repository = repository


def get_security_repository() -> SecurityRepository:
    """Return the active security repository implementation.

    Returns:
        The override repository when configured, otherwise the active provider
        implementation.
    """
    global _override_repository
    if _override_repository is not None:
        return _override_repository
    return _default_security_repository()


def reset_security_repository() -> None:
    """Clear the security repository override and cached default instance.

    Returns:
        ``None``.
    """
    global _override_repository
    _override_repository = None
    _default_security_repository.cache_clear()


@lru_cache(maxsize=1)
def _default_security_repository() -> SecurityRepository:
    """Return the cached default security repository implementation.

    Returns:
        The active provider security repository.
    """
    return store.get_security_repository()
