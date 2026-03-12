"""Repository dependency factories."""

from functools import lru_cache

from api.repositories.admin_repository import AdminRepository
from api.repositories.common_repository import CommonRepository
from api.repositories.coverage_repository import (
    CoverageRepository,
    CoverageRouteRepository,
)
from api.repositories.dashboard_repository import DashboardRepository
from api.repositories.dna_repository import DnaRouteRepository
from api.repositories.home_repository import HomeRepository
from api.repositories.internal_repository import InternalRepository
from api.repositories.rna_repository import RnaRouteRepository, RnaWorkflowRepository
from api.repositories.sample_repository import SampleRepository
from api.repositories.user_repository import UserRepository


@lru_cache
def get_admin_repository() -> AdminRepository:
    """Return the shared admin repository instance.

    Returns:
        The repository used by admin management services and routers.
    """
    return AdminRepository()


@lru_cache
def get_common_repository() -> CommonRepository:
    """Return the shared common-domain repository instance.

    Returns:
        The repository used by common read flows.
    """
    return CommonRepository()


def get_coverage_processing_repository() -> CoverageRepository:
    """Return the repository used for coverage-processing workflows.

    Returns:
        The coverage-processing repository implementation.
    """
    return CoverageRepository()


def get_coverage_repository() -> CoverageRouteRepository:
    """Return the repository used by coverage HTTP routes.

    Returns:
        The route-facing coverage repository implementation.
    """
    return CoverageRouteRepository()


@lru_cache
def get_dashboard_repository() -> DashboardRepository:
    """Return the shared dashboard repository instance.

    Returns:
        The repository used by dashboard services.
    """
    return DashboardRepository()


def get_dna_repository() -> DnaRouteRepository:
    """Return the repository used by DNA and small-variant flows.

    Returns:
        The route-facing DNA repository implementation.
    """
    return DnaRouteRepository()


@lru_cache
def get_home_repository() -> HomeRepository:
    """Return the shared sample-catalog repository instance.

    Returns:
        The repository used by sample catalog and home/sample context flows.
    """
    return HomeRepository()


@lru_cache
def get_internal_repository() -> InternalRepository:
    """Return the shared internal repository instance.

    Returns:
        The repository used by internal support routes.
    """
    return InternalRepository()


def get_rna_repository() -> RnaRouteRepository:
    """Return the repository used by RNA and fusion flows.

    Returns:
        The route-facing RNA repository implementation.
    """
    return RnaRouteRepository()


def get_rna_workflow_repository() -> RnaWorkflowRepository:
    """Return the repository used by RNA workflow orchestration.

    Returns:
        The RNA workflow repository implementation.
    """
    return RnaWorkflowRepository()


def get_user_repository() -> UserRepository:
    """Return the repository used by user service flows.

    Returns:
        The user repository implementation.
    """
    return UserRepository()


def get_sample_repository() -> SampleRepository:
    """Return the repository used by sample mutation flows.

    Returns:
        The sample repository implementation.
    """
    return SampleRepository()
