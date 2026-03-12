"""Ports for workflow services."""

from __future__ import annotations

from typing import Any, Protocol


class RNAWorkflowRepository(Protocol):
    """Define the persistence operations required by RNA workflow services."""

    def update_sample_filters(self, sample_id: str, filters: dict[str, Any]) -> None:
        """Update sample filters.

        Args:
            sample_id (str): Value for ``sample_id``.
            filters (dict[str, Any]): Value for ``filters``.

        Returns:
            None.
        """
        ...

    def get_sample_by_id(self, sample_id: str) -> dict[str, Any] | None:
        """Return sample by id.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        ...

    def get_isgl_by_ids(self, isgl_ids: list[str]) -> dict[str, Any]:
        """Return isgl by ids.

        Args:
            isgl_ids (list[str]): Value for ``isgl_ids``.

        Returns:
            dict[str, Any]: The function result.
        """
        ...

    def get_rna_expression(self, sample_id: str) -> dict[str, Any] | None:
        """Return rna expression.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        ...

    def get_rna_classification(self, sample_id: str) -> dict[str, Any] | None:
        """Return rna classification.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        ...

    def get_rna_qc(self, sample_id: str) -> dict[str, Any] | None:
        """Return rna qc.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        ...

    def get_fusion_in_other_samples(self, fusion: dict[str, Any]) -> list[dict[str, Any]]:
        """Return fusion in other samples.

        Args:
            fusion (dict[str, Any]): Value for ``fusion``.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        ...

    def get_global_annotations(
        self,
        selected_fusion_call: dict[str, Any],
        assay_group: str,
        subpanel: str | None,
    ) -> tuple[Any, Any, Any, Any]:
        """Return global annotations.

        Args:
            selected_fusion_call (dict[str, Any]): Value for ``selected_fusion_call``.
            assay_group (str): Value for ``assay_group``.
            subpanel (str | None): Value for ``subpanel``.

        Returns:
            tuple[Any, Any, Any, Any]: The function result.
        """
        ...

    def hidden_fusion_comments(self, fusion_id: str) -> Any:
        """Handle hidden fusion comments.

        Args:
            fusion_id (str): Value for ``fusion_id``.

        Returns:
            Any: The function result.
        """
        ...

    def get_asp_group_mappings(self) -> dict[str, Any]:
        """Return asp group mappings.

        Returns:
            dict[str, Any]: The function result.
        """
        ...

    def get_sample_fusions(self, fusion_query: dict[str, Any]) -> list[dict[str, Any]]:
        """Return sample fusions.

        Args:
            fusion_query (dict[str, Any]): Value for ``fusion_query``.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        ...

    def get_fusion_annotations(self, fusion: dict[str, Any]) -> tuple[Any, Any]:
        """Return fusion annotations.

        Args:
            fusion (dict[str, Any]): Value for ``fusion``.

        Returns:
            tuple[Any, Any]: The function result.
        """
        ...

