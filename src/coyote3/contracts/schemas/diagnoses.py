"""Shared diagnosis definitions and explicit assay associations."""

from datetime import datetime

from pydantic import Field, field_validator

from coyote3.config.constants import normalize_clinical_identifier
from coyote3.contracts.schemas.base import _StrictCollectionDocBase, _StrictDocBase


class DiagnosisFields(_StrictDocBase):
    """Editable display metadata; retirement does not remove historical references."""

    display_name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    is_active: bool = True

    @field_validator("display_name", "description", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        """Trim submitted text before validating its length."""
        return value.strip() if isinstance(value, str) else value


class DiagnosisCreate(DiagnosisFields):
    """New shared diagnosis identity, independent of its assay associations."""

    diagnosis_id: str = Field(min_length=1, max_length=100)

    @field_validator("diagnosis_id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        """Return a canonical identifier or reject unsupported characters."""
        return normalize_clinical_identifier(value, label="diagnosis_id")


class DiagnosisUpdate(DiagnosisFields):
    """Replacement metadata with an optimistic concurrency precondition."""

    expected_version: int = Field(ge=1)


class SharedDiagnosisCreate(DiagnosisCreate):
    """Create one shared definition and selected assay associations together."""

    asp_ids: list[str] = Field(default_factory=list, max_length=1000)

    @field_validator("asp_ids")
    @classmethod
    def normalize_assays(cls, values: list[str]) -> list[str]:
        """Normalize assay keys and remove duplicate selections."""
        return list(dict.fromkeys(normalize_clinical_identifier(value) for value in values))


class DiagnosisAssociationUpdate(_StrictDocBase):
    """Change only one association's availability with a revision precondition."""

    is_active: bool
    expected_version: int = Field(ge=1)


class SharedDiagnosisUpdate(DiagnosisUpdate):
    """Revise shared metadata and add links without removing or reactivating existing ones."""

    add_asp_ids: list[str] = Field(default_factory=list, max_length=1000)

    @field_validator("add_asp_ids")
    @classmethod
    def normalize_assays(cls, values: list[str]) -> list[str]:
        """Normalize and deduplicate assays requested for association."""
        return list(dict.fromkeys(normalize_clinical_identifier(value) for value in values))


class DiagnosisDefinitionDoc(DiagnosisCreate, _StrictCollectionDocBase):
    """Globally identified display metadata, independent of assay membership."""

    version: int = Field(default=1, ge=1)
    system_installed: bool = False
    is_current: bool = True
    updated_by: str = Field(min_length=1)
    updated_on: datetime


class DiagnosisAssociationDoc(_StrictCollectionDocBase):
    """Revision of an independently enabled assay-to-diagnosis association."""

    asp_id: str
    diagnosis_id: str
    is_active: bool = True
    version: int = Field(default=1, ge=1)
    system_installed: bool = False
    is_current: bool = True
    updated_by: str = Field(min_length=1)
    updated_on: datetime

    @field_validator("asp_id", "diagnosis_id")
    @classmethod
    def normalize_identity(cls, value: str) -> str:
        """Validate stable clinical identifiers without inferring synonyms."""
        return normalize_clinical_identifier(value)


class AssayDiagnosisDoc(DiagnosisCreate, _StrictCollectionDocBase):
    """Joined view of a shared definition and one versioned assay association."""

    asp_id: str
    version: int = Field(default=1, ge=1)
    system_installed: bool = False
    is_current: bool = True
    updated_by: str = Field(min_length=1)
    updated_on: datetime
    definition_is_active: bool = True
    definition_version: int = Field(default=1, ge=1)

    @field_validator("asp_id")
    @classmethod
    def normalize_assay(cls, value: str) -> str:
        """Return the canonical parent-assay business key."""
        return normalize_clinical_identifier(value, label="asp_id")


class DiagnosesPayload(_StrictDocBase):
    """Current definitions, including retired scopes for administrative inspection."""

    diagnoses: list[AssayDiagnosisDoc]


class DiagnosisDefinitionView(DiagnosisDefinitionDoc):
    """Shared definition with all linked assay identifiers, including inactive links."""

    associated_asp_ids: list[str] = Field(default_factory=list)


class DiagnosisDefinitionsPayload(_StrictDocBase):
    """Globally shared current diagnosis metadata."""

    diagnoses: list[DiagnosisDefinitionView]
