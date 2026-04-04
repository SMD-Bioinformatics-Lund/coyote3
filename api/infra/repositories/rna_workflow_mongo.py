"""Mongo-backed repository adapter for RNA workflow service."""

from __future__ import annotations

from typing import Any

from api.extensions import store


class RnaWorkflowRepository:
    """Provide mongo rna workflow persistence operations."""

    def update_sample_filters(self, sample_id: str, filters: dict[str, Any]) -> None:
        """Update sample filters.

        Args:
            sample_id (str): Value for ``sample_id``.
            filters (dict[str, Any]): Value for ``filters``.

        Returns:
            None.
        """
        store.sample_handler.update_sample_filters(sample_id, filters)

    def get_sample_by_id(self, sample_id: str) -> dict[str, Any] | None:
        """Return sample by id.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return store.sample_handler.get_sample_by_id(sample_id)

    def get_isgl_by_ids(self, isgl_ids: list[str]) -> dict[str, Any]:
        """Return isgl by ids.

        Args:
            isgl_ids (list[str]): Value for ``isgl_ids``.

        Returns:
            dict[str, Any]: The function result.
        """
        return store.isgl_handler.get_isgl_by_ids(isgl_ids)

    def get_rna_expression(self, sample_id: str) -> dict[str, Any] | None:
        """Return rna expression.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return store.rna_expression_handler.get_rna_expression(sample_id)

    def get_rna_classification(self, sample_id: str) -> dict[str, Any] | None:
        """Return rna classification.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return store.rna_classification_handler.get_rna_classification(sample_id)

    def get_rna_qc(self, sample_id: str) -> dict[str, Any] | None:
        """Return rna qc.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return store.rna_qc_handler.get_rna_qc(sample_id)

    def get_fusion_in_other_samples(self, fusion: dict[str, Any]) -> list[dict[str, Any]]:
        """Return fusion in other samples.

        Args:
            fusion (dict[str, Any]): Value for ``fusion``.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        return store.fusion_handler.get_fusion_in_other_samples(fusion)

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
        return store.annotation_handler.get_global_annotations(
            selected_fusion_call, assay_group, subpanel
        )

    def hidden_fusion_comments(self, fusion_id: str) -> Any:
        """Hidden fusion comments.

        Args:
            fusion_id (str): Value for ``fusion_id``.

        Returns:
            Any: The function result.
        """
        return store.fusion_handler.hidden_fusion_comments(fusion_id)

    def get_asp_group_mappings(self) -> dict[str, Any]:
        """Return asp group mappings.

        Returns:
            dict[str, Any]: The function result.
        """
        return store.asp_handler.get_asp_group_mappings()

    def get_sample_fusions(self, fusion_query: dict[str, Any]) -> list[dict[str, Any]]:
        """Return sample fusions.

        Args:
            fusion_query (dict[str, Any]): Value for ``fusion_query``.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        return list(store.fusion_handler.get_sample_fusions(fusion_query))

    def get_fusion_annotations(self, fusion: dict[str, Any]) -> tuple[Any, Any]:
        """Return fusion annotations.

        Args:
            fusion (dict[str, Any]): Value for ``fusion``.

        Returns:
            tuple[Any, Any]: The function result.
        """
        return store.fusion_handler.get_fusion_annotations(fusion)
