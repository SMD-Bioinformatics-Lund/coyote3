"""Structural manifests remain independent of center policy and clinical filters."""

import pytest
from coyote.contracts.sample_manifest import SampleCaseControlDoc, SampleFileDoc, SampleManifest
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def test_manifest_normalizes_shared_structure_and_preserves_host_metadata(manifest_payload) -> None:
    manifest = SampleManifest.model_validate(
        {
            **manifest_payload,
            "name": " SYNTHETIC-CASE ",
            "asp_category": " DNA ",
            "asp_family": " Custom-Family ",
            "environment": "center-specific-workflow",
            "platform": "center-platform",
            "sex": " FEMALE ",
            "pipeline_version": " not_provided ",
            "analysis_intents": [" GERMLINE ", "somatic", "germline"],
            "database_versions": {"vep": "v113.1", "gnomad": "N/A"},
            "filters": {"host_specific": {"threshold": 0}},
        }
    )
    assert manifest.name == "SYNTHETIC-CASE"
    assert manifest.asp_family == "custom-family"
    assert manifest.environment == "center-specific-workflow"
    assert manifest.platform == "center-platform"
    assert manifest.sex == "female"
    assert manifest.pipeline_version is None
    assert manifest.analysis_intents == ["germline", "somatic"]
    assert manifest.database_versions == {"vep": "113.1"}
    assert manifest.model_dump()["filters"] == {"host_specific": {"threshold": 0}}


@pytest.mark.parametrize(
    "updates,match",
    [
        ({"case_id": " "}, "case_id"),
        ({"control_id": "SYNTHETIC-CASE", "paired": True, "sample_no": 2}, "must not be the same"),
        ({"paired": True}, "paired must be False"),
        ({"sample_no": 2}, "sample_no must be 1"),
        ({"control": {}}, "control details"),
        ({"control_id": "CONTROL"}, "paired must be True"),
        ({"control_id": "CONTROL", "paired": True}, "sample_no must be 2"),
        ({"sex": "invalid"}, "sex"),
        ({"analysis_intents": ["invalid"]}, "somatic and germline"),
        ({"assay": "example-assay"}, "Retired sample fields"),
        ({"fusion_files": "fusions.tsv"}, "DNA sample must not include RNA"),
        ({"vcf_files": None}, "DNA sample must include"),
        ({"asp_category": "rna"}, "RNA sample must not include DNA"),
        ({"asp_category": "rna", "vcf_files": None}, "RNA sample must include"),
    ],
)
def test_inconsistent_manifests_are_rejected(manifest_payload, updates, match) -> None:
    with pytest.raises(ValidationError, match=match):
        SampleManifest.model_validate({**manifest_payload, **updates})


def test_paired_rna_manifest_is_accepted(manifest_payload) -> None:
    manifest = SampleManifest.model_validate(
        {
            **manifest_payload,
            "asp_category": "rna",
            "vcf_files": None,
            "fusion_files": "fusions.tsv",
            "control_id": "CONTROL",
            "control": {"bam": None},
            "paired": True,
            "sample_no": 2,
            "analysis_intents": "somatic",
        }
    )
    assert set(manifest.files) == {"fusion_files"}
    assert manifest.control.bam == ""


@pytest.mark.parametrize("value", [None, "", [], [None, " "]])
def test_empty_intents_use_somatic_default(manifest_payload, value) -> None:
    manifest = SampleManifest.model_validate({**manifest_payload, "analysis_intents": value})
    assert manifest.analysis_intents == ["somatic"]


@pytest.mark.parametrize("value,expected", [(None, None), (" ", None), (" 1.2 ", "1.2")])
def test_optional_versions_and_sex_keep_missing_values(manifest_payload, value, expected) -> None:
    manifest = SampleManifest.model_validate(
        {**manifest_payload, "pipeline_version": value, "sex": None}
    )
    assert manifest.pipeline_version == expected
    assert manifest.sex is None


def test_invalid_top_level_shape_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SampleManifest.model_validate([])


def test_file_descriptor_validation_and_alignment_paths() -> None:
    descriptor = SampleFileDoc(path=" variants.vcf ", checksum=" ", size_bytes=0)
    assert descriptor.model_dump()["path"] == "variants.vcf"
    assert descriptor.checksum is None
    assert descriptor.size_bytes == 0
    assert SampleCaseControlDoc(bam=None, bai=" file.bai ").model_dump()["bai"] == "file.bai"
    with pytest.raises(ValidationError):
        SampleFileDoc(path=None)
    with pytest.raises(ValidationError):
        SampleFileDoc(path="v.vcf", unknown=True)
    with pytest.raises(ValidationError):
        SampleCaseControlDoc(bam=42)
