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
    return AdminRepository()


@lru_cache
def get_common_repository() -> CommonRepository:
    return CommonRepository()


def get_coverage_processing_repository() -> CoverageRepository:
    return CoverageRepository()


def get_coverage_repository() -> CoverageRouteRepository:
    return CoverageRouteRepository()


@lru_cache
def get_dashboard_repository() -> DashboardRepository:
    return DashboardRepository()


def get_dna_repository() -> DnaRouteRepository:
    return DnaRouteRepository()


@lru_cache
def get_home_repository() -> HomeRepository:
    return HomeRepository()


@lru_cache
def get_internal_repository() -> InternalRepository:
    return InternalRepository()


def get_rna_repository() -> RnaRouteRepository:
    return RnaRouteRepository()


def get_rna_workflow_repository() -> RnaWorkflowRepository:
    return RnaWorkflowRepository()


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_sample_repository() -> SampleRepository:
    return SampleRepository()
