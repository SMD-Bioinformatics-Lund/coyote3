"""Security repository wiring helpers."""

from __future__ import annotations

from api.infra.repositories.security_mongo import MongoSecurityRepository
from api.security.ports import SecurityRepository

_repository: SecurityRepository | None = None


def set_security_repository(repository: SecurityRepository) -> None:
    global _repository
    _repository = repository


def get_security_repository() -> SecurityRepository:
    global _repository
    if _repository is None:
        _repository = MongoSecurityRepository()
    return _repository
