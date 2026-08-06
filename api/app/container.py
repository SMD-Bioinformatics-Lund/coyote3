"""API-owned extension singletons."""

from __future__ import annotations

from typing import Any

from api.app.utilities.common import CommonUtility
from api.app.utilities.dashboard import DashBoardUtility
from api.app.utilities.reporting import ReportUtility
from api.domain.core.repository_protocols import (
    AssayConfigurationRepositoryProtocol,
    SampleRepositoryProtocol,
    VariantsRepositoryProtocol,
)
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
        self.report = ReportUtility()
        self._initialized = True

    def __getattr__(self, name: str) -> Any:
        """Lazy-initialize utility groups on first access."""
        if name in {"common", "dashboard", "report"}:
            self.init_util()
            return object.__getattribute__(self, name)
        raise AttributeError(name)


class _LazyRepositoryProxy:
    """Placeholder object used until runtime initializes the store."""

    def __getattr__(self, _name: str) -> Any:
        def _missing(*_args, **_kwargs):
            raise RuntimeError("Persistence repository used before API runtime initialization")

        return _missing


class MongoStore:
    """Singleton container for the MongoAdapter and its repositories.

    After ``init_from_app`` the adapter's attributes (repositories, collections,
    client, databases) are available directly on this object.
    """

    # Statically declare repository attributes so type checkers and IDEs can
    # understand the runtime-populated store surface.
    annotation_repository: Any
    assay_configuration_repository: AssayConfigurationRepositoryProtocol
    assay_panel_repository: Any
    bam_record_repository: Any
    biomarker_repository: Any
    blacklist_repository: Any
    brca_repository: Any
    clinpgx_public_repository: Any
    civic_repository: Any
    copy_number_variant_repository: Any
    cosmic_repository: Any
    coverage_repository: Any
    expression_repository: Any
    fusion_repository: Any
    grouped_coverage_repository: Any
    hgnc_repository: Any
    iarc_tp53_repository: Any
    gene_list_repository: Any
    oncokb_repository: Any
    permissions_repository: Any
    notification_repository: Any
    reported_variant_repository: Any
    report_repository: Any
    rna_classification_repository: Any
    rna_expression_repository: Any
    rna_quality_repository: Any
    roles_repository: Any
    sample_repository: SampleRepositoryProtocol
    sample_comment_repository: Any
    translocation_repository: Any
    user_repository: Any
    variant_repository: VariantsRepositoryProtocol
    vep_metadata_repository: Any

    _repository_names: tuple[str, ...] = (
        "annotation_repository",
        "assay_configuration_repository",
        "assay_panel_repository",
        "bam_record_repository",
        "biomarker_repository",
        "blacklist_repository",
        "brca_repository",
        "clinpgx_public_repository",
        "civic_repository",
        "copy_number_variant_repository",
        "cosmic_repository",
        "coverage_repository",
        "expression_repository",
        "fusion_repository",
        "grouped_coverage_repository",
        "hgnc_repository",
        "iarc_tp53_repository",
        "gene_list_repository",
        "oncokb_repository",
        "permissions_repository",
        "notification_repository",
        "reported_variant_repository",
        "report_repository",
        "rna_classification_repository",
        "rna_expression_repository",
        "rna_quality_repository",
        "roles_repository",
        "sample_repository",
        "sample_comment_repository",
        "translocation_repository",
        "user_repository",
        "variant_repository",
        "vep_metadata_repository",
    )

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to pre-initialization state."""
        self._adapter: Any | None = None
        self.client = None
        self.coyote_db = None
        self.bam_db = None
        self.annotation_repository = _LazyRepositoryProxy()
        self.assay_configuration_repository = _LazyRepositoryProxy()
        self.assay_panel_repository = _LazyRepositoryProxy()
        self.bam_record_repository = _LazyRepositoryProxy()
        self.biomarker_repository = _LazyRepositoryProxy()
        self.blacklist_repository = _LazyRepositoryProxy()
        self.brca_repository = _LazyRepositoryProxy()
        self.clinpgx_public_repository = _LazyRepositoryProxy()
        self.civic_repository = _LazyRepositoryProxy()
        self.copy_number_variant_repository = _LazyRepositoryProxy()
        self.cosmic_repository = _LazyRepositoryProxy()
        self.coverage_repository = _LazyRepositoryProxy()
        self.expression_repository = _LazyRepositoryProxy()
        self.fusion_repository = _LazyRepositoryProxy()
        self.grouped_coverage_repository = _LazyRepositoryProxy()
        self.hgnc_repository = _LazyRepositoryProxy()
        self.iarc_tp53_repository = _LazyRepositoryProxy()
        self.gene_list_repository = _LazyRepositoryProxy()
        self.oncokb_repository = _LazyRepositoryProxy()
        self.permissions_repository = _LazyRepositoryProxy()
        self.notification_repository = _LazyRepositoryProxy()
        self.reported_variant_repository = _LazyRepositoryProxy()
        self.report_repository = _LazyRepositoryProxy()
        self.rna_classification_repository = _LazyRepositoryProxy()
        self.rna_expression_repository = _LazyRepositoryProxy()
        self.rna_quality_repository = _LazyRepositoryProxy()
        self.roles_repository = _LazyRepositoryProxy()
        self.sample_repository = _LazyRepositoryProxy()
        self.sample_comment_repository = _LazyRepositoryProxy()
        self.translocation_repository = _LazyRepositoryProxy()
        self.user_repository = _LazyRepositoryProxy()
        self.variant_repository = _LazyRepositoryProxy()
        self.vep_metadata_repository = _LazyRepositoryProxy()

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
