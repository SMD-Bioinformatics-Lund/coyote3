"""Mongo-backed repository adapter for admin sample deletion workflow."""

from __future__ import annotations

from typing import Any

from api.extensions import store


class MongoAdminSampleDeletionRepository:
    def get_sample_by_id(self, sample_id: str) -> dict[str, Any] | None:
        return store.sample_handler.get_sample_by_id(sample_id)

    def delete_sample_variants(self, sample_id: str) -> Any:
        return store.variant_handler.delete_sample_variants(sample_id)

    def delete_sample_cnvs(self, sample_id: str) -> Any:
        return store.cnv_handler.delete_sample_cnvs(sample_id)

    def delete_sample_coverage(self, sample_id: str) -> Any:
        return store.coverage_handler.delete_sample_coverage(sample_id)

    def delete_sample_panel_coverage(self, sample_id: str) -> Any:
        return store.coverage2_handler.delete_sample_coverage(sample_id)

    def delete_sample_translocs(self, sample_id: str) -> Any:
        return store.transloc_handler.delete_sample_translocs(sample_id)

    def delete_sample_fusions(self, sample_id: str) -> Any:
        return store.fusion_handler.delete_sample_fusions(sample_id)

    def delete_sample_biomarkers(self, sample_id: str) -> Any:
        return store.biomarker_handler.delete_sample_biomarkers(sample_id)

    def delete_sample(self, sample_id: str) -> Any:
        return store.sample_handler.delete_sample(sample_id)
