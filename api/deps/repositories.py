"""Repository dependency factories for direct route injection."""

from api.infra.repositories import (
    CommonRepository,
    InternalRepository,
    SampleRepository,
)


def get_common_repository() -> CommonRepository:
    """Return the common-domain repository for shared read flows."""
    return CommonRepository()


def get_internal_repository() -> InternalRepository:
    """Return the internal repository for support routes."""
    return InternalRepository()


def get_sample_repository() -> SampleRepository:
    """Return the sample mutation repository."""
    return SampleRepository()
