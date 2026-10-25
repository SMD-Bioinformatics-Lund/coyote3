"""Core repository protocols for dependency injection and type checking."""

from typing import Any, Iterable, Protocol


class SampleRepositoryProtocol(Protocol):
    """Protocol for sample repository operations."""

    def get_samples(
        self,
        *,
        user_assays: list[str] | None = None,
        user_envs: list[str] | None = None,
        status: str | None = None,
        search_str: str | None = None,
        report: bool = False,
        limit: int | None = None,
        offset: int = 0,
        use_cache: bool = True,
        reload: bool = False,
    ) -> Iterable[dict[str, Any]]:
        """Retrieve ready samples within the supplied access and report scope.

        Args:
            user_assays: Allowed assay IDs; None is unscoped and an empty list matches none.
            user_envs: Allowed environments; None is unscoped and an empty list matches none.
            status: Cache/logging label; report controls the reported-state filter.
            search_str: Literal, case-insensitive identity search; null or blank disables it.
            report: Select reported samples when true, otherwise unreported samples.
            limit: Maximum row count; None leaves the result unbounded.
            offset: Number of matching rows to skip, defaulting to zero.
            use_cache: Permit reading and populating the sample cache.
            reload: Bypass a cached result and query storage when true.

        Returns:
            Matching sample dictionaries ordered by descending time_added.
        """
        ...

    def get_samples_page(
        self,
        *,
        user_assays: list[str] | None,
        user_envs: list[str] | None,
        status: str,
        report: bool,
        search_str: str,
        sort: str,
        limit: int,
        offset: int = 0,
        time_limit: Any = None,
        added_from: Any = None,
        added_until: Any = None,
    ) -> dict[str, Any]:
        """Retrieve one sorted ready-sample page and its exact filtered total.

        Args:
            user_assays: Allowed assay IDs; None is unscoped and an empty list matches none.
            user_envs: Allowed environments; None is unscoped and an empty list matches none.
            status: Label for query logging, not a separate sample-state filter.
            report: Select reported samples when true, otherwise unreported samples.
            search_str: Literal, case-insensitive identity search; blank disables it.
            sort: Comma-separated field:direction keys from the sample-list sort vocabulary.
            limit: Positive maximum number of rows in the page.
            offset: Rows to skip; negative values are treated as zero.
            time_limit: Exclusive latest-report timestamp lower bound when report is true.
            added_from: Inclusive time_added lower bound, or None for no bound.
            added_until: Exclusive time_added upper bound, or None for no bound.

        Returns:
            A mapping with items and total. With no recognized sort key, rows
            use descending latest_report_on for reports or time_added otherwise;
            descending document ID breaks ties.
        """
        ...

    def count_ready_samples_by_asp(
        self,
        *,
        user_assays: list[str] | None = None,
        user_envs: list[str] | None = None,
    ) -> dict[str, int]:
        """Count ready samples by assay within the supplied access scope.

        Args:
            user_assays: Allowed assay IDs; None is unscoped and an empty list matches none.
            user_envs: Allowed environments; None is unscoped and an empty list matches none.

        Returns:
            Counts keyed by nonempty assay IDs, omitting assays with no matches.
        """
        ...

    def get_dashboard_sample_rollup(
        self,
        *,
        asp_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Aggregate dashboard sample totals and categorical breakdowns.

        Args:
            asp_ids: Allowed assay IDs; None is unscoped and an empty list matches none.

        Returns:
            Dashboard counters and grouped sample metadata, including recent samples.

        Notes:
            Unlike the ready-sample listing, the rollup includes all ingest states.
        """
        ...


class VariantsRepositoryProtocol(Protocol):
    """Protocol for small variant operations."""

    def get_dashboard_variant_counts(self) -> dict[str, Any]:
        """Aggregate collection-wide small-variant and false-positive counters.

        Returns:
            Estimated total_variants with snv/small_variants aliases, total_snps,
            fps, and by_variant_class counts. Missing classes use Unknown.

        Notes:
            No assay or sample access scope is applied by this operation.
        """
        ...

    def update_selected_transcript(
        self,
        *,
        var_id: str,
        selected_csq: dict[str, Any],
        selected_feature: str,
        criteria: str,
    ) -> Any:
        """Persist the selected consequence and selection provenance for one variant.

        Args:
            var_id: String form of the stored variant's document identifier.
            selected_csq: Consequence payload to store under INFO.selected_CSQ.
            selected_feature: Transcript identifier to store as selected_csq_feature.
            criteria: Selection explanation stored under INFO.selected_CSQ_criteria.

        Returns:
            The repository's structured write result, including matched and modified counts.

        Notes:
            Removes embedded INFO.CSQ and invalidates dashboard metrics when a
            variant matches. The implementation requires a valid document identifier.
        """
        ...


class AssayConfigurationRepositoryProtocol(Protocol):
    """Protocol for assay configuration metadata operations."""

    def get_aspc_revision_no_meta(self, revision_id: object) -> dict[str, Any] | None:
        """Fetch an exact stored ASPC revision without creator/updater metadata.

        Args:
            revision_id: Stored document ID or its string form; None finds no revision.

        Returns:
            The revision without created_on/by and updated_on/by, or None if absent.
            Inactive historical revisions remain eligible.
        """
        ...

    def count_aspcs(self, is_active: bool = False) -> int:
        """Count assay configurations matching an active-state filter.

        Args:
            is_active: True selects active configurations; False selects inactive ones.

        Returns:
            The number of matching configuration documents.

        Notes:
            This protocol declares False as its default. The MongoDB implementation
            defaults to None, which counts both states; pass a boolean explicitly
            when relying on this protocol's active-state selection.
        """
        ...

    def get_dashboard_analysis_type_rollup(
        self,
        *,
        asp_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Count enabled and reportable analyses for selected active assay configurations.

        Args:
            asp_ids: Assay IDs to include; an empty list selects none. Although this
                protocol permits None, the MongoDB implementation requires a list.

        Returns:
            Counts by analysis type. The MongoDB implementation returns a sorted
            list of analysis_type/enabled/reportable records, despite this protocol's
            dictionary return annotation.

        Raises:
            ValueError: If a nonblank assay identifier has invalid syntax.
            TypeError: If None is passed to the MongoDB implementation.
        """
        ...
