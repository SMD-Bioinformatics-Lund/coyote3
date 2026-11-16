"""Manifest validation remains local and reports contract or file failures."""

import json

import pytest
from coyote_ingest.validate import main


@pytest.fixture
def manifest(tmp_path):
    """Create a synthetic DNA manifest using the default core vocabulary."""
    path = tmp_path / "sample.yaml"
    path.write_text(
        json.dumps(
            {
                "name": "SYNTHETIC_INGEST_001",
                "asp_id": "synthetic-assay",
                "diagnosis_id": "base",
                "environment": "testing",
                "case_id": "SYNTHETIC_INGEST_001",
                "sample_no": 1,
                "paired": False,
                "asp_family": "panel-dna",
                "asp_category": "dna",
                "platform": "illumina",
                "pipeline": "SyntheticPipeline",
                "pipeline_version": "1.0",
                "vcf_files": "synthetic.vcf",
            }
        ),
        encoding="utf-8",
    )
    return path


def test_validation_checks_relative_inputs_without_submitting(manifest, capsys):
    with pytest.raises(SystemExit, match="Referenced files missing"):
        main(["--yaml", str(manifest), "--check-files"])

    data_path = manifest.parent / "synthetic.vcf"
    data_path.write_text("##fileformat=VCFv4.2\n", encoding="utf-8")
    assert main(["--yaml", str(manifest), "--check-files", "--list-files"]) == 0
    assert capsys.readouterr().out.strip() == str(data_path.resolve())


def test_validation_prints_normalized_contract_only_when_requested(manifest, capsys):
    assert main(["--yaml", str(manifest), "--json"]) == 0
    status, _, output = capsys.readouterr().out.partition("\n")
    assert status == "[ok] ingest spec is valid"
    payload = json.loads(output)
    assert payload["name"] == "SYNTHETIC_INGEST_001"
    assert payload["files"]["vcf_files"]["path"] == "synthetic.vcf"


@pytest.mark.parametrize("content,error", [("[]", "object"), ("{}", "Spec validation failed")])
def test_validation_rejects_invalid_manifest(tmp_path, content, error):
    path = tmp_path / "invalid.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit, match=error):
        main(["--yaml", str(path)])


def test_validation_rejects_missing_manifest(tmp_path):
    with pytest.raises(SystemExit, match="YAML file not found"):
        main(["--yaml", str(tmp_path / "missing.yaml")])
