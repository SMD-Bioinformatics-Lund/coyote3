"""Manifest validation remains local and reports contract or file failures."""

import json

import pytest

from coyote_relay.validate import main


@pytest.fixture
def manifest(tmp_path):
    """Create a synthetic DNA manifest using the shared manifest structure."""
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
    assert (
        status
        == "[ok] manifest structure is valid; clinical validation is performed by the receiving server"
    )
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


def test_clinical_validation_is_available_in_the_base_install(manifest, capsys):
    assert main(["--yaml", str(manifest), "--clinical"]) == 0
    assert capsys.readouterr().out.strip() == (
        "[ok] manifest passes local core validation; receiving-server checks still apply"
    )


def test_structural_validation_does_not_impose_center_environment_vocabulary(manifest):
    payload = json.loads(manifest.read_text())
    payload["environment"] = "external-center-environment"
    manifest.write_text(json.dumps(payload))
    assert main(["--yaml", str(manifest)]) == 0
    with pytest.raises(SystemExit, match="Spec validation failed"):
        main(["--yaml", str(manifest), "--clinical"])
