"""Admin sample-management and deletion workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.core.admin.sample_deletion import SampleDeletionService, delete_all_sample_traces
from api.extensions import store, util
from api.http import api_error
from api.services.accounts.common import (
    admin_list_pagination,
    current_actor,
    mutation_payload,
    utc_now,
)


class ResourceSampleService:
    """Sample resource workflows."""

    def __init__(self, repository: Any | None = None) -> None:
        """Build the service with an admin repository."""
        self.repository = repository or store.get_admin_repository()
        if repository is None and not SampleDeletionService.has_repository():
            SampleDeletionService.set_repository(store.get_admin_sample_deletion_repository())

    def list_payload(
        self, *, assays: list[str], search: str, page: int = 1, per_page: int = 30
    ) -> dict[str, Any]:
        """List payload.

        Args:
            assays (list[str]): Value for ``assays``.
            search (str): Value for ``search``.

        Returns:
            dict[str, Any]: The function result.
        """
        samples, total = self.repository.list_samples_for_admin(
            assays=assays,
            search=search,
            page=page,
            per_page=per_page,
        )
        return {
            "samples": samples,
            "pagination": admin_list_pagination(
                q=search,
                page=page,
                per_page=per_page,
                total=total,
            ),
        }

    def context_payload(self, *, sample_id: str) -> dict[str, Any]:
        """Context payload.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        sample_doc = self.repository.get_sample(sample_id)
        if not sample_doc:
            raise api_error(404, "Sample not found")
        return {"sample": sample_doc}

    def update(
        self, *, sample_id: str, payload: dict[str, Any], actor_username: str
    ) -> dict[str, Any]:
        """Update.

        Args:
            sample_id (str): Value for ``sample_id``.
            payload (dict[str, Any]): Value for ``payload``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        sample_doc = self.repository.get_sample(sample_id)
        if not sample_doc:
            raise api_error(404, "Sample not found")
        sample_obj = sample_doc.get("_id")
        updated_sample = payload.get("sample", {})
        if not updated_sample:
            raise api_error(400, "Missing sample payload")
        updated_sample["updated_on"] = utc_now()
        updated_sample["updated_by"] = current_actor(actor_username)
        updated_sample = util.records.restore_object_ids(deepcopy(updated_sample))
        updated_sample["_id"] = sample_obj
        self.repository.update_sample(sample_obj, updated_sample)
        return mutation_payload(resource="sample", resource_id=str(sample_obj), action="update")

    def delete(self, *, sample_id: str) -> dict[str, Any]:
        """Delete.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        sample_name = self.repository.get_sample_name(sample_id)
        if not sample_name:
            raise api_error(404, "Sample not found")
        deletion_summary = delete_all_sample_traces(sample_id)
        payload = mutation_payload(resource="sample", resource_id=sample_id, action="delete")
        payload["meta"]["sample_name"] = deletion_summary.get("sample_name") or sample_name
        payload["meta"]["results"] = deletion_summary.get("results", [])
        return payload
