"""Draft isolation, scope readiness, review and publication regression coverage."""

import pytest
from coyote.config.clinical_vocabulary import CLINICAL_VOCABULARY
from coyote.contracts.schemas.assay_setup import AssaySetupContent
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("family", "category"), CLINICAL_VOCABULARY.assay_family_categories.items()
)
def test_setup_derives_missing_modality_from_family(family, category):
    """Managed forms can save every supported family without a readonly modality."""
    panel = dict(
        asp_id="synthetic_assay",
        asp_group="hematology",
        asp_family=family,
        display_name="Synthetic assay",
    )
    result = AssaySetupContent.model_validate({"panel": panel})
    assert result.panel.asp_category == category
    assert "asp_category" not in panel


@pytest.mark.parametrize("family, category", [("panel-dna", "rna"), ("unknown", None)])
def test_setup_rejects_conflicting_modality_and_unknown_family(family, category):
    """Deriving modality does not permit invalid or conflicting family selections."""
    panel = dict(
        asp_id="synthetic_assay",
        asp_group="hematology",
        asp_family=family,
        display_name="Synthetic assay",
    )
    if category is not None:
        panel["asp_category"] = category
    with pytest.raises(ValidationError):
        AssaySetupContent.model_validate({"panel": panel})


def content(**overrides):
    """Return a valid synthetic base-only setup and required report settings."""
    return AssaySetupContent.model_validate(
        {
            "panel": dict(
                asp_id="assay_1",
                asp_group="hematology",
                asp_family="panel-dna",
                asp_category="dna",
                display_name="Synthetic assay",
                expected_files=["vcf_files"],
            ),
            "environments": ["production"],
            "configurations": [
                dict(
                    diagnosis_id="base",
                    environment="production",
                    display_name="Synthetic configuration",
                    analysis_types=["SNV"],
                    filters={"somatic": {"snv": {"min_alt_reads": 5}}},
                    reporting=dict(
                        report_sections=["SNV"],
                        language="sv",
                        report_header="Header",
                        report_method="Method",
                        plots_path="plots",
                        report_folder="reports",
                    ),
                )
            ],
            **overrides,
        }
    )


def test_base_is_default_and_cannot_be_removed():
    assert content().scopes == ["base"]
    assert content(scopes=[]).scopes == ["base"]
    assert content(scopes=["base", "Myeloid", "myeloid"]).scopes == ["base", "myeloid"]


def test_production_is_default_and_cannot_be_removed():
    assert content(environments=[]).environments == ["production"]
    assert content(environments=["development", "production"]).environments == [
        "production",
        "development",
    ]
