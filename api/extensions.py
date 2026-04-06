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

    # Statically declare handler attributes so type checkers and IDEs can
    # understand the runtime-populated store surface.
    annotation_handler: Any
    assay_configuration_handler: Any
    assay_panel_handler: Any
    bam_record_handler: Any
    biomarker_handler: Any
    blacklist_handler: Any
    brca_handler: Any
    civic_handler: Any
    copy_number_variant_handler: Any
    cosmic_handler: Any
    coverage_handler: Any
    expression_handler: Any
    fusion_handler: Any
    grouped_coverage_handler: Any
    hgnc_handler: Any
    iarc_tp53_handler: Any
    gene_list_handler: Any
    oncokb_handler: Any
    permissions_handler: Any
    query_profile_handler: Any
    reported_variant_handler: Any
    rna_classification_handler: Any
    rna_expression_handler: Any
    rna_quality_handler: Any
    roles_handler: Any
    sample_handler: Any
    translocation_handler: Any
    user_handler: Any
    variant_handler: Any
    vep_metadata_handler: Any

    _handler_names: tuple[str, ...] = (
        "annotation_handler",
        "assay_configuration_handler",
        "assay_panel_handler",
        "bam_record_handler",
        "biomarker_handler",
        "blacklist_handler",
        "brca_handler",
        "civic_handler",
        "copy_number_variant_handler",
        "cosmic_handler",
        "coverage_handler",
        "expression_handler",
        "fusion_handler",
        "grouped_coverage_handler",
        "hgnc_handler",
        "iarc_tp53_handler",
        "gene_list_handler",
        "oncokb_handler",
        "permissions_handler",
        "query_profile_handler",
        "reported_variant_handler",
        "rna_classification_handler",
        "rna_expression_handler",
        "rna_quality_handler",
        "roles_handler",
        "sample_handler",
        "translocation_handler",
        "user_handler",
        "variant_handler",
        "vep_metadata_handler",
    )

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to pre-initialization state."""
        self._adapter: Any | None = None
        self.client = None
        self.coyote_db = None
        self.bam_db = None
        self.annotation_handler = _LazyHandlerProxy()
        self.assay_configuration_handler = _LazyHandlerProxy()
        self.assay_panel_handler = _LazyHandlerProxy()
        self.bam_record_handler = _LazyHandlerProxy()
        self.biomarker_handler = _LazyHandlerProxy()
        self.blacklist_handler = _LazyHandlerProxy()
        self.brca_handler = _LazyHandlerProxy()
        self.civic_handler = _LazyHandlerProxy()
        self.copy_number_variant_handler = _LazyHandlerProxy()
        self.cosmic_handler = _LazyHandlerProxy()
        self.coverage_handler = _LazyHandlerProxy()
        self.expression_handler = _LazyHandlerProxy()
        self.fusion_handler = _LazyHandlerProxy()
        self.grouped_coverage_handler = _LazyHandlerProxy()
        self.hgnc_handler = _LazyHandlerProxy()
        self.iarc_tp53_handler = _LazyHandlerProxy()
        self.gene_list_handler = _LazyHandlerProxy()
        self.oncokb_handler = _LazyHandlerProxy()
        self.permissions_handler = _LazyHandlerProxy()
        self.query_profile_handler = _LazyHandlerProxy()
        self.reported_variant_handler = _LazyHandlerProxy()
        self.rna_classification_handler = _LazyHandlerProxy()
        self.rna_expression_handler = _LazyHandlerProxy()
        self.rna_quality_handler = _LazyHandlerProxy()
        self.roles_handler = _LazyHandlerProxy()
        self.sample_handler = _LazyHandlerProxy()
        self.translocation_handler = _LazyHandlerProxy()
        self.user_handler = _LazyHandlerProxy()
        self.variant_handler = _LazyHandlerProxy()
        self.vep_metadata_handler = _LazyHandlerProxy()

    def init_from_app(self, runtime: Any) -> None:
        """Create and initialize the MongoAdapter, then bind its attributes."""
        from pymongo.errors import ConnectionFailure

        from api.infra.mongo.adapter import MongoAdapter

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


store = MongoStore()
ldap_manager = LdapManager()
util = Utility()
