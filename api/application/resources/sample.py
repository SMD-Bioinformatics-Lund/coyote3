"""Admin sample-management and deletion workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from bson import ObjectId

from api.application.accounts.common import (
    admin_list_pagination,
    change_payload,
    current_actor,
    utc_now,
)
from api.application.admin.sample_deletion import delete_all_sample_traces
from api.application.resources.helpers import _validated_doc
from api.domain.common.errors import api_error
from api.infra.observability.operations import measured_operation


class ResourceSampleService:
    """Sample resource workflows."""

    @classmethod
    def from_store(
        cls,
        store: Any,
    ) -> "ResourceSampleService":
        """Build the service from the runtime store."""
        return cls(
            sample_repository=store.sample_repository,
            variant_repository=store.variant_repository,
            copy_number_variant_repository=store.copy_number_variant_repository,
            coverage_repository=store.coverage_repository,
            translocation_repository=store.translocation_repository,
            fusion_repository=store.fusion_repository,
            biomarker_repository=store.biomarker_repository,
            pgx_repository=store.pgx_repository,
            rna_expression_repository=store.rna_expression_repository,
            rna_classification_repository=store.rna_classification_repository,
            rna_quality_repository=store.rna_quality_repository,
            sample_comment_repository=store.sample_comment_repository,
            finding_comment_repository=store.finding_comment_repository,
            report_repository=store.report_repository,
            reported_variant_repository=store.reported_variant_repository,
            assay_panel_repository=store.assay_panel_repository,
        )

    def __init__(
        self,
        *,
        sample_repository: Any,
        variant_repository: Any,
        copy_number_variant_repository: Any,
        coverage_repository: Any,
        translocation_repository: Any,
        fusion_repository: Any,
        biomarker_repository: Any,
        pgx_repository: Any,
        rna_expression_repository: Any,
        rna_classification_repository: Any,
        rna_quality_repository: Any,
        sample_comment_repository: Any,
        finding_comment_repository: Any,
        report_repository: Any,
        reported_variant_repository: Any,
        assay_panel_repository: Any,
    ) -> None:
        """Create the service with explicit injected persistence/util dependencies."""
        self.sample_repository = sample_repository
        self.variant_repository = variant_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.coverage_repository = coverage_repository
        self.translocation_repository = translocation_repository
        self.fusion_repository = fusion_repository
        self.biomarker_repository = biomarker_repository
        self.pgx_repository = pgx_repository
        self.rna_expression_repository = rna_expression_repository
        self.rna_classification_repository = rna_classification_repository
        self.rna_quality_repository = rna_quality_repository
        self.sample_comment_repository = sample_comment_repository
        self.finding_comment_repository = finding_comment_repository
        self.report_repository = report_repository
        self.reported_variant_repository = reported_variant_repository
        self.assay_panel_repository = assay_panel_repository

    @measured_operation("query.samples")
    def list_payload(
        self,
        *,
        asp_ids: list[str] | None,
        search: str,
        asp_group: str = "",
        asp_id: str = "",
        page: int = 1,
        per_page: int = 30,
    ) -> dict[str, Any]:
        """Return the admin sample list payload."""
        panels = [
            dict(item)
            for item in (self.assay_panel_repository.get_all_asps(is_active=True) or [])
            if isinstance(item, dict) and item.get("asp_id")
        ]
        allowed_ids = None if asp_ids is None else set(asp_ids)
        allowed_panels = [
            panel
            for panel in panels
            if allowed_ids is None or str(panel.get("asp_id")) in allowed_ids
        ]
        normalized_group = str(asp_group or "").strip()
        normalized_asp_id = str(asp_id or "").strip()
        group_panels = [
            panel
            for panel in allowed_panels
            if not normalized_group or str(panel.get("asp_group") or "") == normalized_group
        ]
        filtered_ids = [str(panel["asp_id"]) for panel in group_panels]
        if normalized_asp_id:
            filtered_ids = [value for value in filtered_ids if value == normalized_asp_id]
        query_asp_ids = filtered_ids if normalized_group or normalized_asp_id else asp_ids

        rows, total = self.sample_repository.search_samples_for_admin(
            asp_ids=query_asp_ids,
            search_str=search,
            page=page,
            per_page=per_page,
            ready_only=False,
        )
        panels_by_id = {str(panel["asp_id"]): panel for panel in allowed_panels}
        samples = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            sample = dict(item)
            panel = panels_by_id.get(str(sample.get("asp_id") or ""), {})
            case = sample.get("case") if isinstance(sample.get("case"), dict) else {}
            control = sample.get("control") if isinstance(sample.get("control"), dict) else {}
            sample["asp_group"] = panel.get("asp_group")
            sample["asp_category"] = panel.get("asp_category")
            sample["case_clarity_id"] = case.get("clarity_id")
            sample["control_clarity_id"] = control.get("clarity_id")
            samples.append(sample)

        return {
            "samples": samples,
            "filter_options": {
                "asp_group": sorted(
                    {
                        str(panel.get("asp_group"))
                        for panel in allowed_panels
                        if panel.get("asp_group")
                    }
                ),
                "asp_id": sorted({str(panel["asp_id"]) for panel in group_panels}),
            },
            "pagination": admin_list_pagination(
                q=search,
                page=page,
                per_page=per_page,
                total=int(total or 0),
            ),
        }

    def context_payload(self, *, sample_id: str) -> dict[str, Any]:
        """Return the edit context for a single sample."""
        sample_doc = self.sample_repository.get_sample(sample_id)
        if not sample_doc:
            raise api_error(404, "Sample not found")
        return {"sample": sample_doc}

    def update(
        self, *, sample_id: str, payload: dict[str, Any], actor_username: str
    ) -> dict[str, Any]:
        """Update a sample and return a change-status payload."""
        sample_doc = self.sample_repository.get_sample(sample_id)
        if not sample_doc:
            raise api_error(404, "Sample not found")
        sample_obj = sample_doc.get("_id")
        updated_sample = deepcopy(payload.get("sample", {}))
        if not updated_sample:
            raise api_error(400, "Missing sample payload")
        updated_sample["updated_on"] = utc_now()
        updated_sample["updated_by"] = current_actor(actor_username)
        updated_sample = _validated_doc("samples", updated_sample)
        updated_sample = _restore_object_ids(updated_sample)
        updated_sample["_id"] = sample_obj
        self.sample_repository.update_sample(sample_obj, updated_sample)
        sample_name = str(updated_sample.get("name") or sample_doc.get("name") or sample_obj)
        payload = change_payload(resource="sample", resource_id=str(sample_obj), action="update")
        payload["meta"]["sample_name"] = sample_name
        payload["meta"]["sample_oid"] = str(sample_obj)
        return payload

    def delete(self, *, sample_id: str) -> dict[str, Any]:
        """Delete a sample and return a change-status payload."""
        sample_name = self.sample_repository.get_sample_name(sample_id)
        if not sample_name:
            raise api_error(404, "Sample not found")
        deletion_summary = delete_all_sample_traces(
            sample_id,
            sample_repository=self.sample_repository,
            variant_repository=self.variant_repository,
            copy_number_variant_repository=self.copy_number_variant_repository,
            coverage_repository=self.coverage_repository,
            translocation_repository=self.translocation_repository,
            fusion_repository=self.fusion_repository,
            biomarker_repository=self.biomarker_repository,
            pgx_repository=self.pgx_repository,
            rna_expression_repository=self.rna_expression_repository,
            rna_classification_repository=self.rna_classification_repository,
            rna_quality_repository=self.rna_quality_repository,
            sample_comment_repository=self.sample_comment_repository,
            finding_comment_repository=self.finding_comment_repository,
            report_repository=self.report_repository,
            reported_variant_repository=self.reported_variant_repository,
        )
        payload = change_payload(resource="sample", resource_id=sample_id, action="delete")
        payload["meta"]["sample_name"] = deletion_summary.get("sample_name") or sample_name
        payload["meta"]["sample_oid"] = sample_id
        payload["meta"]["results"] = deletion_summary.get("results", [])
        return payload


def _restore_object_ids(value: Any) -> Any:
    """Restore serialized Mongo object identifiers in an admin sample payload."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "_id" and isinstance(item, str):
                value[key] = ObjectId(item)
            else:
                _restore_object_ids(item)
    elif isinstance(value, list):
        for item in value:
            _restore_object_ids(item)
    return value
