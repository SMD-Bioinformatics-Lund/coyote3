"""Admin sample-management and deletion workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.http import api_error
from api.services.accounts.common import (
    admin_list_pagination,
    change_payload,
    current_actor,
    utc_now,
)
from api.services.admin.sample_deletion import delete_all_sample_traces


class ResourceSampleService:
    """Sample resource workflows."""

    @classmethod
    def from_store(
        cls,
        store: Any,
        *,
        records_util: Any,
    ) -> "ResourceSampleService":
        """Build the service from the shared store."""
        return cls(
            sample_handler=store.sample_handler,
            variant_handler=store.variant_handler,
            copy_number_variant_handler=store.copy_number_variant_handler,
            coverage_handler=store.coverage_handler,
            translocation_handler=store.translocation_handler,
            fusion_handler=store.fusion_handler,
            biomarker_handler=store.biomarker_handler,
            records_util=records_util,
        )

    def __init__(
        self,
        *,
        sample_handler: Any,
        variant_handler: Any,
        copy_number_variant_handler: Any,
        coverage_handler: Any,
        translocation_handler: Any,
        fusion_handler: Any,
        biomarker_handler: Any,
        records_util: Any,
    ) -> None:
        """Create the service with explicit injected persistence/util dependencies."""
        self.sample_handler = sample_handler
        self.variant_handler = variant_handler
        self.copy_number_variant_handler = copy_number_variant_handler
        self.coverage_handler = coverage_handler
        self.translocation_handler = translocation_handler
        self.fusion_handler = fusion_handler
        self.biomarker_handler = biomarker_handler
        self.records_util = records_util

    def list_payload(
        self, *, assays: list[str] | None, search: str, page: int = 1, per_page: int = 30
    ) -> dict[str, Any]:
        """Return the admin sample list payload."""
        rows, total = self.sample_handler.search_samples_for_admin(
            assays=assays,
            search_str=search,
            page=page,
            per_page=per_page,
            ready_only=False,
        )
        samples = [dict(item) for item in rows if isinstance(item, dict)]
        return {
            "samples": samples,
            "pagination": admin_list_pagination(
                q=search,
                page=page,
                per_page=per_page,
                total=int(total or 0),
            ),
        }

    def context_payload(self, *, sample_id: str) -> dict[str, Any]:
        """Return the edit context for a single sample."""
        sample_doc = self.sample_handler.get_sample(sample_id)
        if not sample_doc:
            raise api_error(404, "Sample not found")
        return {"sample": sample_doc}

    def update(
        self, *, sample_id: str, payload: dict[str, Any], actor_username: str
    ) -> dict[str, Any]:
        """Update a sample and return a change-status payload."""
        sample_doc = self.sample_handler.get_sample(sample_id)
        if not sample_doc:
            raise api_error(404, "Sample not found")
        sample_obj = sample_doc.get("_id")
        updated_sample = payload.get("sample", {})
        if not updated_sample:
            raise api_error(400, "Missing sample payload")
        updated_sample["updated_on"] = utc_now()
        updated_sample["updated_by"] = current_actor(actor_username)
        updated_sample = self.records_util.restore_object_ids(deepcopy(updated_sample))
        updated_sample["_id"] = sample_obj
        self.sample_handler.update_sample(sample_obj, updated_sample)
        return change_payload(resource="sample", resource_id=str(sample_obj), action="update")

    def delete(self, *, sample_id: str) -> dict[str, Any]:
        """Delete a sample and return a change-status payload."""
        sample_name = self.sample_handler.get_sample_name(sample_id)
        if not sample_name:
            raise api_error(404, "Sample not found")
        deletion_summary = delete_all_sample_traces(
            sample_id,
            sample_handler=self.sample_handler,
            variant_handler=self.variant_handler,
            copy_number_variant_handler=self.copy_number_variant_handler,
            coverage_handler=self.coverage_handler,
            translocation_handler=self.translocation_handler,
            fusion_handler=self.fusion_handler,
            biomarker_handler=self.biomarker_handler,
        )
        payload = change_payload(resource="sample", resource_id=sample_id, action="delete")
        payload["meta"]["sample_name"] = deletion_summary.get("sample_name") or sample_name
        payload["meta"]["results"] = deletion_summary.get("results", [])
        return payload
