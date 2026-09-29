"""Administrative creation of stable assay-group scopes."""

from typing import Any

from api.application.accounts.common import change_payload, utc_now
from api.contracts.schemas.assay_groups import AssayGroupCreate, AssayGroupDoc, AssayGroupStatus
from api.domain.common.errors import api_error


class AssayGroupService:
    """List system definitions and register custom groups without modifying seeds."""

    def __init__(self, repository: Any) -> None:
        """Receive the application database's group repository."""
        self.repository = repository

    def list_payload(self) -> dict:
        """Return both system and custom groups for administration."""
        return {"groups": self.repository.list()}

    def impact(self, group_id: str) -> dict:
        """Return the current revision and affected assays for operator confirmation."""
        group = self.repository.get(group_id)
        if group is None:
            raise api_error(404, "Assay group not found")
        return {"group": group, "assays": self.repository.affected_assays(group_id)}

    def change_status(self, group_id: str, payload: AssayGroupStatus, *, actor: str) -> dict:
        """Apply a confirmed status change and describe it for managed audit logging."""
        previous = self.repository.change_status(
            group_id,
            expected_version=payload.expected_version,
            values={
                "is_active": payload.is_active,
                "status_reason": payload.reason,
                "updated_by": actor,
                "updated_on": utc_now(),
            },
        )
        result = change_payload(resource="assay_group", resource_id=group_id, action="status")
        result["meta"]["revision"] = {
            "previous_version": previous["version"],
            "new_version": previous["version"] + 1,
            "previous_is_active": previous["is_active"],
            "is_active": payload.is_active,
            "reason": payload.reason,
        }
        return result

    def create(self, payload: AssayGroupCreate, *, actor: str) -> dict:
        """Register a custom scope with server-owned provenance.

        Args:
            payload: Validated identifier and public display metadata.
            actor: Authenticated creator recorded in the group and audit event.

        Returns:
            Standard managed-resource change metadata.
        """
        document = AssayGroupDoc(
            **payload.model_dump(), system_managed=False, created_by=actor, created_on=utc_now()
        )
        self.repository.create(document.model_dump(by_alias=True, exclude={"id_"}))
        return change_payload(resource="assay_group", resource_id=payload.group_id, action="create")
