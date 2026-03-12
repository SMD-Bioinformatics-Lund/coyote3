"""Service dependency factories."""

from api.services.sample_service import SampleService
from api.services.user_service import UserService


def get_user_service() -> UserService:
    return UserService()


def get_sample_service() -> SampleService:
    return SampleService()
