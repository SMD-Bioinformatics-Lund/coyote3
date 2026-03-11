"""Mongo-backed repository adapter for RNA workflow service."""

from __future__ import annotations

from typing import Any

from api.extensions import store


class MongoRNAWorkflowRepository:
    def update_sample_filters(self, sample_id: str, filters: dict[str, Any]) -> None:
        store.sample_handler.update_sample_filters(sample_id, filters)

    def get_sample_by_id(self, sample_id: str) -> dict[str, Any] | None:
        return store.sample_handler.get_sample_by_id(sample_id)

    def get_isgl_by_ids(self, isgl_ids: list[str]) -> dict[str, Any]:
        return store.isgl_handler.get_isgl_by_ids(isgl_ids)

    def get_rna_expression(self, sample_id: str) -> dict[str, Any] | None:
        return store.rna_expression_handler.get_rna_expression(sample_id)

    def get_rna_classification(self, sample_id: str) -> dict[str, Any] | None:
        return store.rna_classification_handler.get_rna_classification(sample_id)

    def get_rna_qc(self, sample_id: str) -> dict[str, Any] | None:
        return store.rna_qc_handler.get_rna_qc(sample_id)

    def get_fusion_in_other_samples(self, fusion: dict[str, Any]) -> list[dict[str, Any]]:
        return store.fusion_handler.get_fusion_in_other_samples(fusion)

    def get_global_annotations(
        self,
        selected_fusion_call: dict[str, Any],
        assay_group: str,
        subpanel: str | None,
    ) -> tuple[Any, Any, Any, Any]:
        return store.annotation_handler.get_global_annotations(
            selected_fusion_call, assay_group, subpanel
        )

    def hidden_fusion_comments(self, fusion_id: str) -> Any:
        return store.fusion_handler.hidden_fusion_comments(fusion_id)

    def get_asp_group_mappings(self) -> dict[str, Any]:
        return store.asp_handler.get_asp_group_mappings()

    def get_sample_fusions(self, fusion_query: dict[str, Any]) -> list[dict[str, Any]]:
        return list(store.fusion_handler.get_sample_fusions(fusion_query))

    def get_fusion_annotations(self, fusion: dict[str, Any]) -> tuple[Any, Any]:
        return store.fusion_handler.get_fusion_annotations(fusion)

