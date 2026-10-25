"""Admin sample-management and deletion workflows."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from coyote3.application.accounts.common import (
    admin_list_pagination,
    change_payload,
    current_actor,
    utc_now,
)
from coyote3.application.common.observability import measured_operation
from coyote3.application.resources.helpers import _validated_doc
from coyote3.domain.common.errors import api_error


class ResourceSampleService:
    """Sample resource workflows."""

    @classmethod
    def from_store(
        cls,
        store: Any,
        *,
        sample_deleter: Callable[[str], dict[str, Any]],
    ) -> "ResourceSampleService":
        """Build the service from the runtime store."""
        return cls(
            sample_repository=store.sample_repository,
            assay_panel_repository=store.assay_panel_repository,
            sample_deleter=sample_deleter,
        )

    def __init__(
        self,
        *,
        sample_repository: Any,
        assay_panel_repository: Any,
        sample_deleter: Callable[[str], dict[str, Any]],
    ) -> None:
        """Bind sample administration to repositories and an atomic deletion operation.

        Args:
            sample_repository: Sample metadata search, reads and validated updates.
            assay_panel_repository: Assay definitions used to limit administration views.
            sample_deleter: Deletes sample-owned records and queues artifact erasure,
                returning the committed counts and sample name.
        """
        self.sample_repository = sample_repository
        self.assay_panel_repository = assay_panel_repository
        self.sample_deleter = sample_deleter

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
        """Update sample metadata while preserving server-owned initial attribution.

        Args:
            sample_id: Identifier of the existing sample.
            payload: Replacement sample under the sample key; entry attribution is ignored.
            actor_username: Authenticated editor recorded in the update audit fields.

        Returns:
            Change status with sample identifiers for the administration UI.

        Raises:
            AppError: The sample is missing or replacement content is empty.
            ValueError: The replacement fails sample validation.
        """
        sample_doc = self.sample_repository.get_sample(sample_id)
        if not sample_doc:
            raise api_error(404, "Sample not found")
        sample_obj = sample_doc.get("_id")
        updated_sample = deepcopy(payload.get("sample", {}))
        if not updated_sample:
            raise api_error(400, "Missing sample payload")
        updated_sample["updated_on"] = utc_now()
        updated_sample["updated_by"] = current_actor(actor_username)
        for field in ("created_by", "ingested_by", "ingest_source"):
            updated_sample[field] = sample_doc.get(field)
        updated_sample["system_installed"] = bool(sample_doc.get("system_installed"))
        if "current_aspc_id" in updated_sample and str(updated_sample["current_aspc_id"]) == str(
            sample_doc.get("current_aspc_id")
        ):
            updated_sample["current_aspc_id"] = sample_doc.get("current_aspc_id")
        for field in (
            "asp_id",
            "diagnosis_id",
            "environment",
            "asp_category",
            "asp_family",
            "genome_build",
            "analysis_intents",
            "current_aspc_id",
            "current_aspc_name",
            "aspc_resolution",
            "filters",
            "version",
        ):
            if field in updated_sample and updated_sample[field] != sample_doc.get(field):
                raise api_error(
                    409, f"Use the sample configuration or filter workflow to change '{field}'"
                )
            if field in sample_doc:
                updated_sample[field] = deepcopy(sample_doc[field])
        updated_sample = _validated_doc("samples", updated_sample)
        updated_sample["_id"] = sample_obj
        self.sample_repository.update_sample(sample_obj, updated_sample)
        sample_name = str(updated_sample.get("name") or sample_doc.get("name") or sample_obj)
        payload = change_payload(resource="sample", resource_id=str(sample_obj), action="update")
        payload["meta"]["sample_name"] = sample_name
        payload["meta"]["sample_oid"] = str(sample_obj)
        return payload

    def delete(self, *, sample_id: str) -> dict[str, Any]:
        """Delete owned database records and queue generated report files for erasure."""
        sample_name = self.sample_repository.get_sample_name(sample_id)
        if not sample_name:
            raise api_error(404, "Sample not found")
        deletion_summary = self.sample_deleter(sample_id)
        payload = change_payload(resource="sample", resource_id=sample_id, action="delete")
        payload["meta"]["sample_name"] = deletion_summary.get("sample_name") or sample_name
        payload["meta"]["sample_oid"] = sample_id
        payload["meta"]["results"] = deletion_summary.get("results", [])
        payload["meta"]["report_artifacts_queued"] = deletion_summary.get(
            "report_artifacts_queued", 0
        )
        return payload
