"""Canonical user repository."""

from api.infra.repositories.security_mongo import MongoSecurityRepository as UserRepository

__all__ = ["UserRepository"]
