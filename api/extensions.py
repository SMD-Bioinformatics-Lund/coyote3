"""API-owned extension singletons."""

from __future__ import annotations

from typing import Any

from api.common.dashboard_utility import DashBoardUtility
from api.common.managed_records import ManagedRecordUtility
from api.common.report_util import ReportUtility
from api.common.utility import CommonUtility
from api.infra.integrations.ldap import LdapManager


class Utility:
    """Utility container used by API routes and services."""

    _initialized: bool = False

    def init_util(self) -> None:
        """Initialize utility groups on first use."""
        if self._initialized:
            return
        self.common = CommonUtility()
        self.dashboard = DashBoardUtility()
        self.records = ManagedRecordUtility()
        self.report = ReportUtility()
        self._initialized = True

    def __getattr__(self, name: str) -> Any:
        """Lazy-initialize utility groups on first access."""
        if name in {"common", "dashboard", "records", "report"}:
            self.init_util()
            return object.__getattribute__(self, name)
        raise AttributeError(name)


class _LazyHandlerProxy:
    """Placeholder object used until runtime initializes the store."""

    def __getattr__(self, _name: str) -> Any:
        def _missing(*_args, **_kwargs):
            raise RuntimeError("Persistence handler used before API runtime initialization")

        return _missing


class MongoStore:
    """Singleton container for the MongoAdapter and its handlers.

    After ``init_from_app`` the adapter's attributes (handlers, collections,
    client, databases) are available directly on this object.
    """

    _handler_names: tuple[str, ...] = (
        "annotation_handler",
        "aspc_handler",
        "asp_handler",
        "bam_service_handler",
        "biomarker_handler",
        "blacklist_handler",
        "brca_handler",
        "civic_handler",
        "cnv_handler",
        "cosmic_handler",
        "coverage_handler",
        "expression_handler",
        "fusion_handler",
        "groupcov_handler",
        "hgnc_handler",
        "iarc_tp53_handler",
        "isgl_handler",
        "oncokb_handler",
        "permissions_handler",
        "query_profiles_handler",
        "reported_variants_handler",
        "rna_classification_handler",
        "rna_expression_handler",
        "rna_qc_handler",
        "roles_handler",
        "sample_handler",
        "transloc_handler",
        "user_handler",
        "variant_handler",
        "vep_meta_handler",
    )

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to pre-initialization state."""
        self._adapter: Any | None = None
        self.client = None
        self.coyote_db = None
        self.bam_db = None
        for name in self._handler_names:
            setattr(self, name, _LazyHandlerProxy())

    def init_from_app(self, runtime: Any) -> None:
        """Create and initialize the MongoAdapter, then bind its attributes."""
        from pymongo.errors import ConnectionFailure

        from api.infra.db.mongo import MongoAdapter

        adapter = MongoAdapter()
        adapter.init_from_app(runtime)
        try:
            adapter.client.admin.command("ping")
        except ConnectionFailure as exc:
            runtime.logger.error("MongoDB connection failed: %s", exc)
            raise RuntimeError("Could not connect to MongoDB.") from exc
        self._adapter = adapter
        for name, value in adapter.__dict__.items():
            if not name.startswith("_"):
                setattr(self, name, value)

    # -- Repository factories (direct, no provider indirection) --

    def get_admin_repository(self):
        from api.infra.repositories.admin_repository import AdminRepository

        return AdminRepository()

    def get_admin_sample_deletion_repository(self):
        from api.infra.repositories.admin_sample_mongo import AdminSampleDeletionRepository

        return AdminSampleDeletionRepository()

    def get_coverage_repository(self):
        from api.infra.repositories.coverage_mongo import CoverageRepository

        return CoverageRepository()

    def get_coverage_route_repository(self):
        from api.infra.repositories.coverage_route_mongo import CoverageRouteRepository

        return CoverageRouteRepository()

    def get_dashboard_repository(self):
        from api.infra.repositories.dashboard_mongo import DashboardRepository

        return DashboardRepository()

    def get_dna_route_repository(self):
        from api.infra.repositories.dna_repository import DnaRouteRepository

        return DnaRouteRepository()

    def get_dna_reporting_repository(self):
        from api.infra.repositories.dna_reporting_mongo import ReportRepository

        return ReportRepository()

    def get_home_repository(self):
        from api.infra.repositories.home_mongo import HomeRepository

        return HomeRepository()

    def get_internal_ingest_repository(self):
        from api.infra.repositories.internal_ingest_mongo import InternalIngestRepository

        return InternalIngestRepository()

    def get_interpretation_repository(self):
        from api.infra.repositories.core_store_mongo import MongoCoreStoreRepository

        return MongoCoreStoreRepository()

    def get_public_catalog_repository(self):
        from api.infra.repositories.public_catalog_mongo import PublicCatalogRepository

        return PublicCatalogRepository()

    def get_reporting_persistence_repository(self):
        from api.infra.repositories.core_store_mongo import MongoCoreStoreRepository

        return MongoCoreStoreRepository()

    def get_rna_route_repository(self):
        from api.infra.repositories.rna_repository import RnaRouteRepository

        return RnaRouteRepository()

    def get_rna_workflow_repository(self):
        from api.infra.repositories.rna_workflow_mongo import RnaWorkflowRepository

        return RnaWorkflowRepository()

    def get_sample_repository(self):
        from api.infra.repositories.samples_mongo import SampleRepository

        return SampleRepository()

    def get_security_repository(self):
        from api.infra.repositories.security_mongo import UserRepository

        return UserRepository()


store = MongoStore()
ldap_manager = LdapManager()
util = Utility()
