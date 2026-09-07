"""Sample-owned alignment references and the explicitly retained lookup fallback."""

from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from api.application.common.alignment_files import alignment_files_payload
from api.application.ingest.helpers import build_sample_meta_dict
from api.contracts.schemas.samples import SampleCaseControlDoc


@pytest.mark.parametrize("value", [None, "", "  "])
def test_missing_alignment_references_are_empty_strings(value):
    assert SampleCaseControlDoc().bam == ""
    assert SampleCaseControlDoc(bam=value, bai=value).model_dump()["bai"] == ""
    assert SampleCaseControlDoc(bam=value, bai=value).bam == ""


@pytest.mark.parametrize("value", [42, [], {}])
def test_alignment_references_reject_non_strings(value):
    with pytest.raises(ValidationError):
        SampleCaseControlDoc(bam=value)


def test_flat_pipeline_references_become_case_control_metadata():
    result = build_sample_meta_dict(
        {
            "case_id": "synthetic_case",
            "control_id": "synthetic_control",
            "case_bam": "/alignments/case.bam",
            "case_bai": "/indexes/case.bai",
            "control_bam": "/alignments/control.bam",
            "control_bai": None,
        }
    )
    case = SampleCaseControlDoc.model_validate(result["case"])
    control = SampleCaseControlDoc.model_validate(result["control"])
    assert case.bam == "/alignments/case.bam"
    assert case.bai == "/indexes/case.bai"
    assert control.bam == "/alignments/control.bam"
    assert control.bai == ""
    assert "case_bam" not in result


def test_explicit_bams_do_not_query_fallback():
    lookup = Mock(side_effect=AssertionError("Unexpected BAM lookup"))
    result = alignment_files_payload(
        {"case": {"bam": "/case.bam", "bai": "/case.bai"}, "control": {"bam": "/control.bam"}},
        {"case": "C", "control": "N"},
        lookup,
    )
    assert result == {
        "bam_id": {"C": ["/case.bam"], "N": ["/control.bam"]},
        "bai_id": {"/case.bam": "/case.bai"},
    }
    lookup.assert_not_called()


def test_metadata_rebuild_preserves_paths_unless_explicitly_cleared():
    sample = {"case_id": "C", "case": {"bam": "/case.bam", "bai": "/case.bai"}}
    assert build_sample_meta_dict(sample)["case"]["bam"] == "/case.bam"
    cleared = build_sample_meta_dict({**sample, "case_bam": None, "case_bai": ""})
    assert cleared["case"]["bam"] == ""
    assert cleared["case"]["bai"] == ""
    replaced = build_sample_meta_dict({**sample, "case_bam": "/new-case.bam"})
    assert replaced["case"]["bam"] == "/new-case.bam"
    assert replaced["case"]["bai"] == ""


def test_mixed_sample_queries_only_missing_role():
    lookup = Mock(return_value={"N": ["/old-control.bam"]})
    result = alignment_files_payload(
        {"case": {"bam": "/case.bam"}, "control": {"bai": "/control.bai"}},
        {"case": "C", "control": "N"},
        lookup,
    )
    lookup.assert_called_once_with({"control": "N"})
    assert result["bam_id"] == {"C": ["/case.bam"], "N": ["/old-control.bam"]}
    assert result["bai_id"] == {"/old-control.bam": "/control.bai"}


def test_old_samples_keep_lookup_without_guessing_index_associations():
    lookup = Mock(return_value={"C": ["/one.bam", "/two.bam"]})
    result = alignment_files_payload(
        {"case": {"bai": "/ambiguous.bai"}},
        {"case": "C"},
        lookup,
    )
    assert result["bam_id"]["C"] == ["/one.bam", "/two.bam"]
    assert result["bai_id"] == {}
    assert alignment_files_payload({}, {}, lookup) == {"bam_id": {}, "bai_id": {}}
