"""Manage assay subpanels without changing existing clinical records."""

from typing import Any

from api.application.accounts.common import change_payload, utc_now
from api.application.resources.availability import require_active_group
from api.config.constants import SUBPANEL_BASE_ID, normalize_clinical_identifier
from api.contracts.schemas.subpanels import (
    SharedSubpanelCreate,
    SharedSubpanelUpdate,
    SubpanelAssociationUpdate,
    SubpanelCreate,
    SubpanelUpdate,
)
from api.domain.common.errors import api_error


class SubpanelService:
    """Manage shared definitions and independently versioned assay associations."""

    def __init__(self, *, panels: Any, subpanels: Any) -> None:
        """Receive the assay and subpanel repositories."""
        self.panels = panels
        self.subpanels = subpanels

    @classmethod
    def from_store(cls, store: Any) -> "SubpanelService":
        """Resolve application-owned repositories from the runtime store."""
        return cls(panels=store.assay_panel_repository, subpanels=store.assay_subpanel_repository)

    def _assay(self, asp_id: str) -> str:
        """Resolve an active parent assay or reject the operation with HTTP 404."""
        try:
            asp_id = normalize_clinical_identifier(asp_id, label="asp_id")
        except ValueError as exc:
            raise api_error(422, "Invalid assay identifier") from exc
        if not self.panels.get_asp(asp_id):
            raise api_error(404, "Active assay not found")
        return asp_id

    def list_payload(self, asp_id: str) -> dict:
        """Return current definitions for an active assay, including retired scopes."""
        return {"subpanels": self.subpanels.list_for_assay(self._assay(asp_id))}

    def definitions_payload(self) -> dict:
        """List globally shared metadata for selection and explicit administration."""
        associations = self.subpanels.assays_by_subpanel()
        return {
            "subpanels": [
                dict(row, associated_asp_ids=associations.get(row["subpanel_id"], []))
                for row in self.subpanels.list_definitions()
            ]
        }

    def create_definition(self, payload: SharedSubpanelCreate, *, actor: str) -> dict:
        """Create a shared scope after validating every selected assay.

        Args:
            payload: Metadata and selected assay identifiers; no selections is allowed.
            actor: Authenticated operator attributed to all created records.

        Returns:
            Change response including selected assays for the audit event.
        """
        if payload.subpanel_id == SUBPANEL_BASE_ID:
            raise api_error(409, "Base is implicit")
        assays = [self._assay(asp_id) for asp_id in payload.asp_ids]
        for asp_id in assays:
            require_active_group(self.panels, self.panels.get_asp(asp_id)["asp_group"])
        self.subpanels.create_definition(
            payload.model_dump(exclude={"asp_ids"})
            | {"updated_by": actor, "updated_on": utc_now()},
            assays,
        )
        result = change_payload(
            resource="subpanel", resource_id=payload.subpanel_id, action="create"
        )
        result["meta"]["asp_ids"] = assays
        result["meta"]["revision"] = {"new_version": 1, "asp_ids": assays}
        return result

    def set_association_status(
        self, asp_id: str, subpanel_id: str, payload: SubpanelAssociationUpdate, *, actor: str
    ) -> dict:
        """Change one assay link without accepting shared metadata from the caller.

        Args:
            asp_id: Parent assay identifier.
            subpanel_id: Existing shared definition identifier.
            payload: Target availability and expected association revision.
            actor: Authenticated operator recorded on the new revision.

        Returns:
            Change response for the association's audit event.

        Raises:
            AppError: The association is absent or its revision has changed.
        """
        asp_id = self._assay(asp_id)
        current = self.subpanels.get_current(asp_id, subpanel_id)
        if current is None:
            raise api_error(404, "Assay association not found")
        return self.save(
            asp_id,
            SubpanelUpdate(
                display_name=current["display_name"],
                description=current.get("description", ""),
                is_active=payload.is_active,
                expected_version=payload.expected_version,
            ),
            actor=actor,
            subpanel_id=subpanel_id,
        )

    def revise_definition(
        self, subpanel_id: str, payload: SharedSubpanelUpdate, *, actor: str
    ) -> dict:
        """Update shared metadata and add assays without removing existing links.

        Args:
            subpanel_id: Stable global key.
            payload: Replacement metadata, expected revision and optional new assay links.
            actor: Authenticated operator recorded in the revision.

        Returns:
            Administrative change metadata for audit logging.
        """
        if subpanel_id == SUBPANEL_BASE_ID:
            raise api_error(409, "Base is implicit")
        assays = [self._assay(asp_id) for asp_id in payload.add_asp_ids]
        for asp_id in assays:
            require_active_group(self.panels, self.panels.get_asp(asp_id)["asp_group"])
        self.subpanels.revise_definition(
            subpanel_id,
            payload.model_dump(exclude={"expected_version", "add_asp_ids"})
            | {"updated_by": actor, "updated_on": utc_now()},
            expected_version=payload.expected_version,
            add_asp_ids=assays,
        )
        result = change_payload(resource="subpanel", resource_id=subpanel_id, action="update")
        result["meta"]["revision"] = {
            "previous_version": payload.expected_version,
            "new_version": payload.expected_version + 1,
            "requested_assay_additions": assays,
        }
        return result

    def save(
        self,
        asp_id: str,
        payload: SubpanelCreate | SubpanelUpdate,
        *,
        actor: str,
        subpanel_id: str | None = None,
    ) -> dict:
        """Create or revise a scope without changing its stable identity.

        Args:
            asp_id: Parent assay business key.
            payload: Validated metadata and, for updates, expected revision.
            actor: Authenticated operator recorded on the revision.
            subpanel_id: Existing identity for updates; omitted for creation.

        Returns:
            Managed change result carrying the new revision for audit logging.
        """
        asp_id = self._assay(asp_id)
        expected = payload.expected_version if isinstance(payload, SubpanelUpdate) else None
        if payload.is_active:
            require_active_group(self.panels, self.panels.get_asp(asp_id)["asp_group"])
        values = payload.model_dump(exclude={"expected_version"})
        try:
            identity = normalize_clinical_identifier(
                subpanel_id or values["subpanel_id"], label="subpanel_id"
            )
        except ValueError as exc:
            raise api_error(422, "Invalid subpanel identifier") from exc
        if identity == SUBPANEL_BASE_ID:
            raise api_error(409, "Base is implicit and cannot be created, edited or retired")
        document = {
            **values,
            "asp_id": asp_id,
            "subpanel_id": identity,
            "version": (expected or 0) + 1,
            "is_current": True,
            "updated_by": actor,
            "updated_on": utc_now(),
        }
        self.subpanels.save(document, expected_version=expected)
        result = change_payload(
            resource="assay_subpanel",
            resource_id=f"{asp_id}/{identity}",
            action="update" if expected else "create",
        )
        result["meta"]["revision"] = {
            "previous_version": expected,
            "new_version": document["version"],
        }
        return result
