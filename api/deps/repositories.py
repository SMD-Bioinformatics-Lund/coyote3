"""Repository dependency factories."""

from api.repositories.sample_repository import SampleRepository
from api.repositories.user_repository import UserRepository


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_sample_repository() -> SampleRepository:
    return SampleRepository()
