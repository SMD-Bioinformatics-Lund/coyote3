"""Admin sample-management and deletion workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.application.accounts.common import (
    admin_list_pagination,
    change_payload,
    current_actor,
    utc_now,
)
from api.application.admin.sample_deletion import delete_all_sample_traces
from api.domain.common.errors import api_error


class ResourceSampleService:
    """Sample resource workflows."""

    @classmethod
    def from_store(
        cls,
        store: Any,
        *,
        records_util: Any,
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
            records_util=records_util,
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
        records_util: Any,
    ) -> None:
        """Create the service with explicit injected persistence/util dependencies."""
        self.sample_repository = sample_repository
        self.variant_repository = variant_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.coverage_repository = coverage_repository
        self.translocation_repository = translocation_repository
        self.fusion_repository = fusion_repository
        self.biomarker_repository = biomarker_repository
        self.records_util = records_util

    def list_payload(
        self, *, asp_ids: list[str] | None, search: str, page: int = 1, per_page: int = 30
    ) -> dict[str, Any]:
        """Return the admin sample list payload."""
        rows, total = self.sample_repository.search_samples_for_admin(
            asp_ids=asp_ids,
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
        updated_sample = payload.get("sample", {})
        if not updated_sample:
            raise api_error(400, "Missing sample payload")
        updated_sample["updated_on"] = utc_now()
        updated_sample["updated_by"] = current_actor(actor_username)
        updated_sample = self.records_util.restore_object_ids(deepcopy(updated_sample))
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
        )
        payload = change_payload(resource="sample", resource_id=sample_id, action="delete")
        payload["meta"]["sample_name"] = deletion_summary.get("sample_name") or sample_name
        payload["meta"]["sample_oid"] = sample_id
        payload["meta"]["results"] = deletion_summary.get("results", [])
        return payload
