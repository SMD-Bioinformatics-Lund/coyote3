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


def test_explicit_filenames_use_the_catalog_directory():
    lookup = Mock(
        return_value={"C": ["panel/BAM/old-case.bam"], "N": ["panel/BAM/old-control.bam"]}
    )
    result = alignment_files_payload(
        {"case": {"bam": "/case.bam", "bai": "/case.bai"}, "control": {"bam": "/control.bam"}},
        {"case": "C", "control": "N"},
        lookup,
    )
    assert result == {
        "design_bed_paths": [],
        "bam_id": {"C": ["panel/BAM/case.bam"], "N": ["panel/BAM/control.bam"]},
        "bai_id": {"panel/BAM/case.bam": "panel/BAM/case.bai"},
    }
    lookup.assert_called_once_with({"case": "C", "control": "N"})


def test_explicit_paths_supply_only_the_basename_and_duplicate_folders_are_collapsed():
    lookup = Mock(return_value={"C": ["panel/BAM/old-1.bam", "panel/BAM/old-2.bam"]})
    result = alignment_files_payload(
        {"case": {"bam": "/pipeline/output/custom.bam", "bai": "C:\\indexes\\custom.bai"}},
        {"case": "C"},
        lookup,
    )
    assert result == {
        "design_bed_paths": [],
        "bam_id": {"C": ["panel/BAM/custom.bam"]},
        "bai_id": {"panel/BAM/custom.bam": "panel/BAM/custom.bai"},
    }


def test_missing_catalog_directory_does_not_guess_a_workstation_path():
    assert alignment_files_payload(
        {"case": {"bam": "custom.bam"}}, {"case": "C"}, Mock(return_value={})
    ) == {"bam_id": {}, "bai_id": {}, "design_bed_paths": []}


def test_metadata_rebuild_preserves_paths_unless_explicitly_cleared():
    sample = {"case_id": "C", "case": {"bam": "/case.bam", "bai": "/case.bai"}}
    assert build_sample_meta_dict(sample)["case"]["bam"] == "/case.bam"
    cleared = build_sample_meta_dict({**sample, "case_bam": None, "case_bai": ""})
    assert cleared["case"]["bam"] == ""
    assert cleared["case"]["bai"] == ""
    replaced = build_sample_meta_dict({**sample, "case_bam": "/new-case.bam"})
    assert replaced["case"]["bam"] == "/new-case.bam"
    assert replaced["case"]["bai"] == ""


def test_mixed_sample_preserves_old_filename_only_for_missing_role():
    lookup = Mock(return_value={"C": ["/old-case.bam"], "N": ["/old-control.bam"]})
    result = alignment_files_payload(
        {"case": {"bam": "/case.bam"}, "control": {"bai": "/control.bai"}},
        {"case": "C", "control": "N"},
        lookup,
    )
    lookup.assert_called_once_with({"case": "C", "control": "N"})
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
    assert alignment_files_payload({}, {}, lookup) == {
        "bam_id": {},
        "bai_id": {},
        "design_bed_paths": [],
    }


def test_asp_directories_resolve_explicit_filenames_without_catalog():
    lookup = Mock(side_effect=AssertionError("Catalog must not be queried"))
    result = alignment_files_payload(
        {"case": {"bam": "case.bam", "bai": "case.bai"}, "control": {"bam": "control.bam"}},
        {"case": "C", "control": "N"},
        lookup,
        asp={
            "igv": {"base_folder": "gmshem", "bam_subfolder": "bam", "design_bed": "BED/design.bed"}
        },
    )
    assert result == {
        "bam_id": {"C": ["gmshem/bam/case.bam"], "N": ["gmshem/bam/control.bam"]},
        "bai_id": {"gmshem/bam/case.bam": "gmshem/bam/case.bai"},
        "design_bed_paths": ["gmshem/BED/design.bed"],
    }
    lookup.assert_not_called()


def test_asp_uses_fallback_only_for_missing_filenames_and_can_omit_bed():
    lookup = Mock(return_value={"N": ["old/bam/control.bam"]})
    result = alignment_files_payload(
        {"case": {"bam": "case.bam"}},
        {"case": "C", "control": "N"},
        lookup,
        asp={"igv": {"base_folder": "tumwgs", "bam_subfolder": "bam", "design_bed": ""}},
    )
    lookup.assert_called_once_with({"control": "N"})
    assert result["bam_id"] == {"C": ["tumwgs/bam/case.bam"], "N": ["old/bam/control.bam"]}
    assert result["design_bed_paths"] == []


@pytest.mark.parametrize(
    "path",
    [
        "/absolute",
        "../escape",
        "a/../escape",
        "C:/data",
        "http://host",
        "a\\b",
        "a//b",
        "a%2fb",
        " ",
    ],
)
def test_asp_igv_rejects_unsafe_relative_paths(path):
    from api.contracts.schemas.assay import AspIgvDoc

    with pytest.raises(ValidationError):
        AspIgvDoc(base_folder=path)


def test_asp_igv_allows_empty_optional_subfolder_and_bed():
    from api.contracts.schemas.assay import AspIgvDoc

    assert AspIgvDoc(base_folder="panel").model_dump() == {
        "base_folder": "panel",
        "bam_subfolder": "",
        "design_bed": "",
    }
