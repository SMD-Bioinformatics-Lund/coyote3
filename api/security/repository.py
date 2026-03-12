"""Security repository wiring helpers."""

from __future__ import annotations

from functools import lru_cache

from api.infra.repositories.security_mongo import MongoSecurityRepository
from api.security.ports import SecurityRepository

_override_repository: SecurityRepository | None = None


def set_security_repository(repository: SecurityRepository) -> None:
    global _override_repository
    _override_repository = repository


def get_security_repository() -> SecurityRepository:
    global _override_repository
    if _override_repository is not None:
        return _override_repository
    return _default_security_repository()


def reset_security_repository() -> None:
    global _override_repository
    _override_repository = None
    _default_security_repository.cache_clear()


@lru_cache(maxsize=1)
def _default_security_repository() -> SecurityRepository:
    return MongoSecurityRepository()
