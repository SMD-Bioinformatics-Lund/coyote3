"""Resolve a sample's resource context from its selected configuration and assay."""

from typing import Any

from pydantic import ValidationError

from api.config.constants import DIAGNOSIS_BASE_ID, normalize_clinical_identifier
from api.contracts.schemas.assay_context import AssayContextDoc
from api.domain.common.errors import setup_error


def build_assay_context(
    sample: dict[str, Any], panel: dict[str, Any], configuration: dict[str, Any]
) -> dict[str, Any]:
    """Capture explicit resource identities and revisions for a configuration receipt.

    Args:
        sample: Requested assay, diagnosis and environment for the sample.
        panel: Referenced assay definition, including its revision and modality/family.
        configuration: Resolved configuration revision, including group and enabled analyses.

    Returns:
        Validated runtime context suitable for immutable report receipts.

    Raises:
        AppError: Resource relationships disagree or required metadata is absent or invalid.
    """
    assay_id = normalize_clinical_identifier(sample["asp_id"], label="asp_id")
    if panel.get("asp_id") != assay_id or configuration.get("asp_id") != assay_id:
        raise setup_error("Assay context does not match the selected sample assay")
    if configuration.get("asp_group") != panel.get("asp_group"):
        raise setup_error("Configuration group does not match the selected assay")
    if sample.get("environment") != configuration.get("environment"):
        raise setup_error("Configuration environment does not match the sample")
    requested = sample.get("diagnosis_id") or DIAGNOSIS_BASE_ID
    resolved = configuration.get("diagnosis_id") or DIAGNOSIS_BASE_ID
    if requested != resolved and resolved != DIAGNOSIS_BASE_ID:
        raise setup_error("Configuration diagnosis does not match the sample")
    if sample.get("asp_category") and sample["asp_category"] != panel.get("asp_category"):
        raise setup_error("Configuration modality does not match the sample")
    if sample.get("asp_family") and sample["asp_family"] != panel.get("asp_family"):
        raise setup_error("Configuration assay family does not match the sample")
    if set(sample.get("analysis_intents") or []) - set(configuration.get("analysis_intents") or []):
        raise setup_error("Configuration does not enable the sample's analysis intents")
    reference = str(configuration.get("reference_genome") or "").lower().removeprefix("grch")
    if sample.get("genome_build") and reference and str(sample["genome_build"]) != reference:
        raise setup_error("Configuration reference assembly does not match the sample")
    values = dict(
        group_id=configuration.get("asp_group"),
        assay_id=assay_id,
        assay_revision=panel.get("version"),
        modality=panel.get("asp_category"),
        family=panel.get("asp_family"),
        diagnosis_id=normalize_clinical_identifier(
            sample.get("diagnosis_id") or DIAGNOSIS_BASE_ID, label="diagnosis_id"
        ),
        environment=configuration.get("environment"),
        configuration_id=configuration.get("aspc_id"),
        configuration_revision=configuration.get("version"),
        analyses=configuration.get("analysis_types"),
        intents=configuration.get("analysis_intents"),
        reference_genome=configuration.get("reference_genome"),
    )
    try:
        return AssayContextDoc.model_validate(values).model_dump()
    except ValidationError as error:
        raise setup_error(
            "Assay configuration has incomplete or inconsistent resource context",
            "Check the registered resource revisions, modality, family and enabled analyses.",
        ) from error
