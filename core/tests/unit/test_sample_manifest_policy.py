"""Clinical sample validation remains stricter than portable manifest structure."""

import pytest
from coyote.contracts.sample_manifest import SampleManifest
from coyote.contracts.schemas.samples import SamplesDoc
from pydantic import ValidationError


@pytest.fixture
def manifest() -> dict:
    """Return a valid synthetic single-case DNA manifest."""
    return {
        "name": "SYNTHETIC-CASE",
        "asp_id": "example-assay",
        "environment": "production",
        "asp_family": "panel-dna",
        "asp_category": "dna",
        "case_id": "SYNTHETIC-CASE",
        "sample_no": 1,
        "pipeline": "example-pipeline",
        "vcf_files": "variants.vcf.gz",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("environment", "unconfigured-environment"),
        ("asp_family", "unconfigured-family"),
        ("platform", "unconfigured-platform"),
        ("read_mode", "unconfigured-read-mode"),
    ],
)
def test_center_vocabulary_is_enforced_only_by_clinical_host(manifest, field, value) -> None:
    payload = {**manifest, field: value}
    assert getattr(SampleManifest.model_validate(payload), field) == value
    with pytest.raises(ValidationError):
        SamplesDoc.model_validate(payload)


def test_rna_germline_remains_rejected_by_clinical_host(manifest) -> None:
    payload = {
        **manifest,
        "asp_category": "rna",
        "asp_family": "wts",
        "vcf_files": None,
        "fusion_files": "fusions.tsv",
        "analysis_intents": ["germline"],
    }
    assert SampleManifest.model_validate(payload).analysis_intents == ["germline"]
    with pytest.raises(ValidationError, match="only for DNA SNV"):
        SamplesDoc.model_validate(payload)


def test_clinical_normalization_preserves_persistence_and_file_metadata(manifest) -> None:
    sample = SamplesDoc.model_validate(
        {
            **manifest,
            "asp_id": "EXAMPLE-ASSAY",
            "environment": " PRODUCTION ",
            "platform": "ILLUMINA",
            "read_mode": "pe",
            "latest_report_id": "synthetic-report",
            "comments": ["not embedded"],
            "uploaded_file_checksums": {"vcf_files": "synthetic-checksum"},
        }
    )
    record = sample.to_persistence_document()
    assert record["asp_id"] == "example-assay"
    assert record["environment"] == "production"
    assert record["read_mode"] == "PE"
    assert record["read_technology"] == "short_read"
    assert record["reported"] is True
    assert "comments" not in record
    assert record["files"]["vcf_files"]["checksum"] == "synthetic-checksum"
