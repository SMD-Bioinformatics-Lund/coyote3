"""Resolved resource identity captured when a sample receives a configuration."""

from typing import Literal

from pydantic import Field, model_validator

from api.config.clinical_vocabulary import CLINICAL_VOCABULARY
from api.contracts.schemas.base import _StrictDocBase


class AssayContextDoc(_StrictDocBase):
    """Interpretation context independent of later edits to resource metadata."""

    group_id: str = Field(min_length=1)
    assay_id: str = Field(min_length=1)
    assay_revision: int = Field(ge=1)
    modality: Literal["dna", "rna"]
    family: str = Field(min_length=1)
    diagnosis_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    configuration_revision: int = Field(ge=1)
    analyses: list[str]
    intents: list[str]
    reference_genome: str | None = None

    @model_validator(mode="after")
    def validate_capability_context(self) -> "AssayContextDoc":
        """Require an implemented family/modality combination and analysis subset.

        Returns:
            This receipt unchanged when its dimensions are compatible.

        Raises:
            ValueError: Family, modality or enabled analyses are inconsistent.
        """
        if CLINICAL_VOCABULARY.assay_family_categories.get(self.family) != self.modality:
            raise ValueError("Resource context family does not support its modality")
        allowed = CLINICAL_VOCABULARY.analysis_types_by_family[self.family]
        if set(self.analyses) - set(allowed):
            raise ValueError("Resource context contains unsupported analyses")
        return self
