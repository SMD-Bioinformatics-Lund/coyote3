"""Mongo-backed repository adapter for DNA reporting workflow."""

from __future__ import annotations

from typing import Any

from api.extensions import store


class MongoDNAReportingRepository:
    def get_asp(self, asp_name: str) -> dict[str, Any] | None:
        return store.asp_handler.get_asp(asp_name=asp_name)

    def get_isgl_by_asp(self, assay: str, *, is_active: bool = True) -> list[dict[str, Any]]:
        return list(store.isgl_handler.get_isgl_by_asp(assay, is_active=is_active) or [])

    def get_isgl_by_ids(self, genelists: list[str]) -> list[dict[str, Any]]:
        return list(store.isgl_handler.get_isgl_by_ids(genelists) or [])

    def get_case_variants(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        return list(store.variant_handler.get_case_variants(query) or [])

    def add_blacklist_data(self, variants: list[dict[str, Any]], assay: str) -> list[dict[str, Any]]:
        return store.blacklist_handler.add_blacklist_data(variants, assay=assay)

    def get_latest_sample_comment(self, sample_id: str) -> dict[str, Any] | None:
        return store.sample_handler.get_latest_sample_comment(sample_id=sample_id)

    def get_interesting_sample_cnvs(self, sample_id: str) -> list[dict[str, Any]]:
        return list(store.cnv_handler.get_interesting_sample_cnvs(sample_id=sample_id) or [])

    def get_sample_biomarkers(self, sample_id: str) -> list[dict[str, Any]]:
        return list(store.biomarker_handler.get_sample_biomarkers(sample_id=sample_id) or [])

    def get_interesting_sample_translocations(self, sample_id: str) -> list[dict[str, Any]]:
        return list(store.transloc_handler.get_interesting_sample_translocations(sample_id=sample_id) or [])

    def get_variant_class_translations(self, vep_version: int) -> dict[str, Any]:
        return store.vep_meta_handler.get_variant_class_translations(vep_version)

