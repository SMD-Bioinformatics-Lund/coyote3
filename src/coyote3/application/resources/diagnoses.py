"""Manage assay diagnoses without changing existing clinical records."""

from typing import Any

from coyote3.application.accounts.common import change_payload, utc_now
from coyote3.application.common.protected_records import reject_system_managed_change
from coyote3.application.common.record_attribution import attribute_record
from coyote3.application.resources.availability import require_active_group
from coyote3.application.resources.helpers import require_new_identifier
from coyote3.config.constants import DIAGNOSIS_BASE_ID, normalize_clinical_identifier
from coyote3.contracts.schemas.diagnoses import (
    DiagnosisAssociationUpdate,
    DiagnosisCreate,
    DiagnosisUpdate,
    SharedDiagnosisCreate,
    SharedDiagnosisUpdate,
)
from coyote3.domain.common.errors import api_error


class DiagnosisService:
    """Manage shared definitions and independently versioned assay associations."""

    def __init__(self, *, panels: Any, diagnoses: Any) -> None:
        """Receive the assay and diagnosis repositories."""
        self.panels = panels
        self.diagnoses = diagnoses

    @classmethod
    def from_store(cls, store: Any) -> "DiagnosisService":
        """Resolve application-owned repositories from the runtime store."""
        return cls(panels=store.assay_panel_repository, diagnoses=store.assay_diagnosis_repository)

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
        return {"diagnoses": self.diagnoses.list_for_assay(self._assay(asp_id))}

    def definitions_payload(self) -> dict:
        """List globally shared metadata for selection and explicit administration."""
        associations = self.diagnoses.assays_by_diagnosis()
        return {
            "diagnoses": [
                dict(row, associated_asp_ids=associations.get(row["diagnosis_id"], []))
                for row in self.diagnoses.list_definitions()
            ]
        }

    def create_definition(self, payload: SharedDiagnosisCreate, *, actor: str) -> dict:
        """Create a shared scope after validating every selected assay.

        Args:
            payload: Metadata and selected assay identifiers; no selections is allowed.
            actor: Authenticated operator attributed to all created records.

        Returns:
            Change response including selected assays for the audit event.
        """
        if payload.diagnosis_id == DIAGNOSIS_BASE_ID:
            raise api_error(409, "Base is implicit")
        require_new_identifier(payload.diagnosis_id, label="diagnosis_id")
        assays = [self._assay(asp_id) for asp_id in payload.asp_ids]
        for asp_id in assays:
            require_active_group(self.panels, self.panels.get_asp(asp_id)["asp_group"])
        self.diagnoses.create_definition(
            attribute_record(payload.model_dump(exclude={"asp_ids"}), actor=actor)
            | {"updated_on": utc_now()},
            assays,
        )
        result = change_payload(
            resource="diagnosis", resource_id=payload.diagnosis_id, action="create"
        )
        result["meta"]["asp_ids"] = assays
        result["meta"]["revision"] = {"new_version": 1, "asp_ids": assays}
        return result

    def set_association_status(
        self, asp_id: str, diagnosis_id: str, payload: DiagnosisAssociationUpdate, *, actor: str
    ) -> dict:
        """Change one assay link without accepting shared metadata from the caller.

        Args:
            asp_id: Parent assay identifier.
            diagnosis_id: Existing shared definition identifier.
            payload: Target availability and expected association revision.
            actor: Authenticated operator recorded on the new revision.

        Returns:
            Change response for the association's audit event.

        Raises:
            AppError: The association is absent or its revision has changed.
        """
        asp_id = self._assay(asp_id)
        current = self.diagnoses.get_current(asp_id, diagnosis_id)
        if current is None:
            raise api_error(404, "Assay association not found")
        return self.save(
            asp_id,
            DiagnosisUpdate(
                display_name=current["display_name"],
                description=current.get("description", ""),
                is_active=payload.is_active,
                expected_version=payload.expected_version,
            ),
            actor=actor,
            diagnosis_id=diagnosis_id,
        )

    def revise_definition(
        self, diagnosis_id: str, payload: SharedDiagnosisUpdate, *, actor: str
    ) -> dict:
        """Update shared metadata and add assays without removing existing links.

        Args:
            diagnosis_id: Stable global key.
            payload: Replacement metadata, expected revision and optional new assay links.
            actor: Authenticated operator recorded in the revision.

        Returns:
            Administrative change metadata for audit logging.
        """
        if diagnosis_id == DIAGNOSIS_BASE_ID:
            raise api_error(409, "Base is implicit")
        current = next(
            (
                row
                for row in self.diagnoses.list_definitions()
                if row["diagnosis_id"] == diagnosis_id
            ),
            None,
        )
        if current is None:
            raise api_error(404, "Diagnosis definition not found")
        reject_system_managed_change(current, resource="diagnosis definition")
        assays = [self._assay(asp_id) for asp_id in payload.add_asp_ids]
        for asp_id in assays:
            require_active_group(self.panels, self.panels.get_asp(asp_id)["asp_group"])
        self.diagnoses.revise_definition(
            diagnosis_id,
            attribute_record(
                payload.model_dump(exclude={"expected_version", "add_asp_ids"}),
                actor=actor,
                previous=current,
            )
            | {"updated_on": utc_now()},
            expected_version=payload.expected_version,
            add_asp_ids=assays,
        )
        result = change_payload(resource="diagnosis", resource_id=diagnosis_id, action="update")
        result["meta"]["revision"] = {
            "previous_version": payload.expected_version,
            "new_version": payload.expected_version + 1,
            "requested_assay_additions": assays,
        }
        return result

    def save(
        self,
        asp_id: str,
        payload: DiagnosisCreate | DiagnosisUpdate,
        *,
        actor: str,
        diagnosis_id: str | None = None,
    ) -> dict:
        """Create or revise a scope without changing its stable identity.

        Args:
            asp_id: Parent assay business key.
            payload: Validated metadata and, for updates, expected revision.
            actor: Authenticated operator recorded on the revision.
            diagnosis_id: Existing identity for updates; omitted for creation.

        Returns:
            Managed change result carrying the new revision for audit logging.
        """
        asp_id = self._assay(asp_id)
        expected = payload.expected_version if isinstance(payload, DiagnosisUpdate) else None
        if isinstance(payload, DiagnosisCreate):
            require_new_identifier(payload.diagnosis_id, label="diagnosis_id")
        if payload.is_active:
            require_active_group(self.panels, self.panels.get_asp(asp_id)["asp_group"])
        values = payload.model_dump(exclude={"expected_version"})
        try:
            identity = normalize_clinical_identifier(
                diagnosis_id or values["diagnosis_id"], label="diagnosis_id"
            )
        except ValueError as exc:
            raise api_error(422, "Invalid diagnosis identifier") from exc
        if identity == DIAGNOSIS_BASE_ID:
            raise api_error(409, "Base is implicit and cannot be created, edited or retired")
        current = self.diagnoses.get_current(asp_id, identity) if expected is not None else None
        if current is not None:
            reject_system_managed_change(current, resource="diagnosis association")
        document = {
            **values,
            "asp_id": asp_id,
            "diagnosis_id": identity,
            "version": (expected or 0) + 1,
            "is_current": True,
            "updated_by": actor,
            "updated_on": utc_now(),
        }
        document = attribute_record(document, actor=actor, previous=current)
        self.diagnoses.save(document, expected_version=expected)
        result = change_payload(
            resource="assay_diagnosis",
            resource_id=f"{asp_id}/{identity}",
            action="update" if expected else "create",
        )
        result["meta"]["revision"] = {
            "previous_version": expected,
            "new_version": document["version"],
        }
        return result
