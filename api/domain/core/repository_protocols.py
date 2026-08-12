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
    ) -> Iterable[dict[str, Any]]: ...

    def count_live_samples_by_asp(
        self,
        *,
        user_assays: list[str] | None = None,
        user_envs: list[str] | None = None,
    ) -> dict[str, int]: ...

    def get_dashboard_sample_rollup(
        self,
        *,
        asp_ids: list[str] | None = None,
    ) -> dict[str, Any]: ...


class VariantsRepositoryProtocol(Protocol):
    """Protocol for small variant operations."""

    def get_dashboard_variant_counts(self) -> dict[str, Any]: ...

    def get_unique_variant_quality_counts(self) -> dict[str, Any]: ...

    def update_selected_transcript(
        self,
        *,
        var_id: str,
        selected_csq: dict[str, Any],
        selected_feature: str,
        criteria: str,
    ) -> Any: ...


class AssayConfigurationRepositoryProtocol(Protocol):
    """Protocol for assay configuration metadata operations."""

    def get_aspc_revision_no_meta(self, revision_id: object) -> dict[str, Any] | None: ...

    def count_aspcs(self, is_active: bool = False) -> int: ...

    def get_dashboard_analysis_type_rollup(
        self,
        *,
        asp_ids: list[str] | None = None,
    ) -> dict[str, Any]: ...
