"""Infrastructure repository adapters — single data-access layer."""

from api.infra.repositories.admin_repository import AdminRepository
from api.infra.repositories.admin_sample_mongo import AdminSampleDeletionRepository
from api.infra.repositories.common_mongo import CommonRepository
from api.infra.repositories.coverage_mongo import CoverageRepository
from api.infra.repositories.coverage_route_mongo import CoverageRouteRepository
from api.infra.repositories.dashboard_mongo import DashboardRepository
from api.infra.repositories.dna_reporting_mongo import ReportRepository
from api.infra.repositories.dna_repository import DnaRouteRepository
from api.infra.repositories.home_mongo import HomeRepository
from api.infra.repositories.internal_ingest_mongo import InternalIngestRepository
from api.infra.repositories.internal_mongo import InternalRepository
from api.infra.repositories.public_catalog_mongo import PublicCatalogRepository
from api.infra.repositories.rna_repository import RnaRouteRepository
from api.infra.repositories.rna_workflow_mongo import RnaWorkflowRepository
from api.infra.repositories.samples_mongo import SampleRepository
from api.infra.repositories.security_mongo import UserRepository

__all__ = [
    "AdminRepository",
    "AdminSampleDeletionRepository",
    "CommonRepository",
    "CoverageRepository",
    "CoverageRouteRepository",
    "DashboardRepository",
    "DnaRouteRepository",
    "HomeRepository",
    "InternalRepository",
    "InternalIngestRepository",
    "PublicCatalogRepository",
    "ReportRepository",
    "RnaRouteRepository",
    "RnaWorkflowRepository",
    "SampleRepository",
    "UserRepository",
]
