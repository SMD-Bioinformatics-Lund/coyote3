"""Embedded SnpEff selection preserves evidence and enforces sample ownership."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.application.dna.structural_variants import DnaStructuralService
from coyote.domain.common.errors import AppError
from coyote.domain.dna.structural_annotations import (
    annotation_key,
    select_structural_annotation,
    structural_transcript_rows,
)


def test_partner_mane_matches_do_not_cross_between_genes():
    """Each partner uses its own transcript and HGNC MANE metadata."""
    ann = {"Gene_Name": "A&B", "Feature_ID": "ENST000001.2&ENST000002.3"}
    genes = {"A": {"ensembl_mane_select": "ENST000001"}, "B": {"ensembl_mane_select": "ENST000001"}}
    row = structural_transcript_rows([ann], {}, genes)[0]
    assert row["partners"][0]["mane_flags"] == ["ensembl_mane_select"]
    assert row["partners"][1]["mane_flags"] == []
    assert row["annotation_key"] == annotation_key(ann)
    assert "partners" not in ann


def test_ingest_does_not_accept_swapped_partner_mane_accessions():
    """Two correct accessions assigned to the wrong genes are not a MANE combination."""
    ann = {
        "Gene_Name": "A&B",
        "Gene_ID": "1&2",
        "Feature_ID": "ENST000002&ENST000001",
        "Transcript_BioType": "protein_coding",
    }
    genes = {"A": {"ensembl_mane_select": "ENST000001"}, "B": {"ensembl_mane_select": "ENST000002"}}
    _, criterion = select_structural_annotation([ann], {}, genes)
    assert criterion == "first_protein_coding"


def test_ingest_prefers_a_row_matching_both_partners_over_one_partner():
    """A single MANE-matching gene cannot select a fusion transcript combination."""
    partial = {
        "Gene_Name": "A&B",
        "Gene_ID": "1&2",
        "Feature_ID": "ENST000001&ENST000099",
        "Transcript_BioType": "protein_coding",
    }
    complete = {**partial, "Feature_ID": "ENST000001.2&ENST000002.3"}
    genes = {"A": {"ensembl_mane_select": "ENST000001"}, "B": {"ensembl_mane_select": "ENST000002"}}
    selected, criterion = select_structural_annotation([partial, complete], {}, genes)
    assert selected == complete
    assert criterion == "ensembl_mane_select"


@pytest.mark.parametrize(
    "owner,key,status",
    [
        ("other", "missing", 404),
        ("sample", "missing", 422),
    ],
)
def test_selection_rejects_unowned_or_unavailable_annotation(owner, key, status):
    """Reject invalid requests before reaching persistence."""
    repo = SimpleNamespace(
        get_transloc=lambda _: {"SAMPLE_ID": owner, "INFO": {"ANN": []}}, select_annotation=Mock()
    )
    service = DnaStructuralService.__new__(DnaStructuralService)
    service.translocation_repository = repo
    with pytest.raises(AppError) as exc:
        service.select_translocation_transcript(sample={"_id": "sample"}, transloc_id="id", key=key)
    assert exc.value.status_code == status
    repo.select_annotation.assert_not_called()
