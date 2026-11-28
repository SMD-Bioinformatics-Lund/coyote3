# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""API-owned extension singletons."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from coyote.domain.repository_protocols import (
    AssayConfigurationRepositoryProtocol,
    SampleRepositoryProtocol,
    VariantsRepositoryProtocol,
)

from coyote_api.infra.integrations.ldap import LdapManager

if TYPE_CHECKING:
    from coyote_mongo.repositories.ingest_jobs import IngestJobsRepository
    from coyote_mongo.repositories.reported_variants import ReportedVariantsRepository
    from coyote_mongo.repositories.reports import ReportRepository
    from coyote_mongo.repositories.users import UsersRepository
    from coyote_mongo.runtime_adapter import MongoAdapter

    from coyote_api.app.runtime_setup import ApiRuntimeContext


class _LazyRepositoryProxy:
    """Placeholder object used until runtime initializes the store."""

    def __getattr__(self, _name: str) -> Any:
        """Return a callable that rejects repository use before initialization.

        Args:
            _name: Requested repository member, ignored by this placeholder.

        Returns:
            A callable that raises RuntimeError when invoked, not on lookup.
        """

        def _missing(*_args: object, **_kwargs: object) -> None:
            """Reject calls to an uninitialized repository.

            Args:
                *_args: Positional repository arguments, ignored.
                **_kwargs: Keyword repository arguments, ignored.

            Raises:
                RuntimeError: Always, because persistence has not been initialized.
            """
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
    edit_lease_repository: Any
    assay_configuration_repository: AssayConfigurationRepositoryProtocol
    assay_panel_repository: Any
    assay_diagnosis_repository: Any
    configuration_profile_repository: Any
    assay_group_repository: Any
    bam_record_repository: Any
    biomarker_repository: Any
    pgx_repository: Any
    ingest_jobs_repository: IngestJobsRepository
    public_assay_catalog_repository: Any
    public_assay_catalog_version_repository: Any
    public_assay_catalog_revision_repository: Any
    blacklist_repository: Any
    brca_repository: Any
    clinpgx_public_repository: Any
    clinical_rule_revision_repository: Any
    clinical_rule_set_repository: Any
    query_rule_repository: Any
    civic_repository: Any
    copy_number_variant_repository: Any
    cosmic_repository: Any
    knowledgebase_version_repository: Any
    d4_coverage_repository: Any
    coverage_repository: Any
    expression_repository: Any
    fusion_repository: Any
    d4_coverage_blacklist_repository: Any
    hgnc_repository: Any
    iarc_tp53_repository: Any
    gene_list_repository: Any
    oncokb_repository: Any
    permissions_repository: Any
    notification_repository: Any
    reported_variant_repository: ReportedVariantsRepository
    report_repository: ReportRepository
    rna_classification_repository: Any
    rna_expression_repository: Any
    rna_quality_repository: Any
    roles_repository: Any
    sample_repository: SampleRepositoryProtocol
    sample_comment_repository: Any
    finding_comment_repository: Any
    translocation_repository: Any
    user_repository: UsersRepository
    variant_repository: VariantsRepositoryProtocol
    vep_metadata_repository: Any

    _repository_names: tuple[str, ...] = (
        "ingest_jobs_repository",
        "annotation_repository",
        "assay_configuration_repository",
        "assay_panel_repository",
        "assay_diagnosis_repository",
        "configuration_profile_repository",
        "assay_group_repository",
        "bam_record_repository",
        "biomarker_repository",
        "pgx_repository",
        "public_assay_catalog_repository",
        "public_assay_catalog_version_repository",
        "public_assay_catalog_revision_repository",
        "blacklist_repository",
        "brca_repository",
        "clinpgx_public_repository",
        "clinical_rule_revision_repository",
        "clinical_rule_set_repository",
        "query_rule_repository",
        "civic_repository",
        "copy_number_variant_repository",
        "cosmic_repository",
        "knowledgebase_version_repository",
        "d4_coverage_repository",
        "coverage_repository",
        "expression_repository",
        "fusion_repository",
        "d4_coverage_blacklist_repository",
        "hgnc_repository",
        "iarc_tp53_repository",
        "gene_list_repository",
        "edit_lease_repository",
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
        "finding_comment_repository",
        "translocation_repository",
        "user_repository",
        "variant_repository",
        "vep_metadata_repository",
    )

    _adapter: MongoAdapter | None

    def __init__(self) -> None:
        """Initialize empty database handles and deferred-failure repository proxies."""
        self.reset()

    def reset(self) -> None:
        """Close any bound adapter and replace database handles and repository proxies."""
        previous = getattr(self, "_adapter", None)
        self._adapter = None
        for name in getattr(self, "_bound_names", ()):
            self.__dict__.pop(name, None)
        self._bound_names: set[str] = set()
        self.client = None
        self.coyote_db = None
        self.identity_db = None
        self.knowledgebase_db = None
        self.bam_db = None
        for name in self._repository_names:
            setattr(self, name, _LazyRepositoryProxy())
        if previous is not None:
            previous.close()

    def init_from_app(self, runtime: ApiRuntimeContext) -> None:
        """Initialize and ping a Mongo adapter before exposing its public attributes.

        Args:
            runtime: API runtime supplying cached package settings, logger and optional cache.

        Raises:
            RuntimeError: The adapter ping raises ConnectionFailure; the new
                adapter is closed and the failure is logged before raising.

        Notes:
            Failed setup preserves the previous binding. Successful replacement
            closes the old adapter and removes its public attributes.
        """
        from coyote_mongo.runtime_adapter import MongoAdapter
        from pymongo.errors import ConnectionFailure

        from coyote_api.infra.observability.prometheus_metrics import observe_operation

        adapter = MongoAdapter(operation_observer=observe_operation)
        try:
            adapter.initialize(
                runtime.backend_settings.mongo,
                logger=runtime.logger,
                cache=runtime.cache,
            )
            adapter.ping()
        except ConnectionFailure as exc:
            adapter.close()
            runtime.logger.error("MongoDB connection failed: %s", exc)
            raise RuntimeError("Could not connect to MongoDB.") from exc
        except BaseException:
            adapter.close()
            raise
        try:
            self.reset()
        except BaseException:
            adapter.close()
            raise
        self._adapter = adapter
        for name, value in adapter.__dict__.items():
            if not name.startswith("_"):
                setattr(self, name, value)
                self._bound_names.add(name)


store = MongoStore()
ldap_manager = LdapManager()
