"""YAML envelope and file descriptor normalization regressions."""

from copy import deepcopy

import pytest
import yaml
from coyote.contracts.manifests import (
    normalize_manifest_files,
    normalize_null_placeholders,
    parse_yaml_payload,
)

pytestmark = pytest.mark.unit


def test_pipeline_fields_and_null_markers_are_normalized() -> None:
    result = parse_yaml_payload(
        "name: SYNTHETIC\nassay: assay-a\ndiagnosis: base\nprofile: development\n"
        "sequencing_technology: illumina\ncase:\n  bam: 'null'\n"
        "control_id: ' N/A '\nnested: [42, false, ' retained ', 'nil']\n"
    )
    assert result == {
        "name": "SYNTHETIC",
        "asp_id": "assay-a",
        "diagnosis_id": "base",
        "environment": "development",
        "platform": "illumina",
        "case": {"bam": None},
        "control_id": None,
        "nested": [42, False, "retained", None],
    }


@pytest.mark.parametrize("text", ["[]", "null", "plain text", "{}", "unrelated: true"])
def test_invalid_envelope_is_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        parse_yaml_payload(text)


def test_invalid_yaml_is_rejected() -> None:
    with pytest.raises(yaml.YAMLError):
        parse_yaml_payload("name: [")


def test_field_alias_conflicts_are_rejected() -> None:
    with pytest.raises(ValueError, match="conflicting values"):
        parse_yaml_payload("name: S\nassay: a\nasp_id: b")
    assert parse_yaml_payload("name: S\nassay: a\nasp_id: a")["asp_id"] == "a"
    assert parse_yaml_payload("name: S\nassay: null\nasp_id: a")["asp_id"] == "a"


def test_normalization_preserves_missing_zero_and_false() -> None:
    assert normalize_null_placeholders([None, 0, False, "NONE", "0"]) == [None, 0, False, None, "0"]


def test_file_checksums_do_not_mutate_input_or_replace_explicit_checksum() -> None:
    data = {
        "files": {"cnv": {"path": "cnv.tsv", "checksum": "explicit"}},
        "vcf_files": {"path": "snv.vcf.gz"},
        "uploaded_file_checksums": {"vcf_files": "uploaded", "cnv": "ignored", "absent": "x"},
    }
    original = deepcopy(data)
    result = normalize_manifest_files(data)
    assert data == original
    assert result == {
        "files": {
            "cnv": {"path": "cnv.tsv", "checksum": "explicit"},
            "vcf_files": {"path": "snv.vcf.gz", "checksum": "uploaded"},
        }
    }


@pytest.mark.parametrize("key", ["hrd", "msi", "tmb"])
def test_separate_biomarker_paths_are_rejected(key: str) -> None:
    with pytest.raises(ValueError, match="one biomarkers JSON"):
        normalize_manifest_files({key: "result.json"})


def test_non_mapping_file_input_is_left_for_schema_validation() -> None:
    assert normalize_manifest_files(None) is None
    assert normalize_manifest_files({"vcf_files": "v.vcf", "uploaded_file_checksums": []}) == {
        "files": {"vcf_files": {"path": "v.vcf"}}
    }
