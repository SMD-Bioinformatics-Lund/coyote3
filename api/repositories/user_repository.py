"""User/security repository facade."""

from api.infra.repositories.security_mongo import MongoSecurityRepository


class UserRepository(MongoSecurityRepository):
    """Concrete user/security repository facade."""


__all__ = ["UserRepository"]
