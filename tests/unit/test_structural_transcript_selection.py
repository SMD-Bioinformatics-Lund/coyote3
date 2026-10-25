"""Embedded SnpEff selection preserves evidence and enforces sample ownership."""

from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from bson import ObjectId

from api.infra.mongo.repositories.translocations import TranslocsRepository
from coyote3.application.dna.structural_variants import DnaStructuralService
from coyote3.domain.common.errors import AppError
from coyote3.domain.dna.structural_annotations import (
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


def test_embedded_selection_preserves_rows_and_checks_concurrent_updates():
    """Only the owning sample's unchanged annotation array can be reordered."""
    collection = mongomock.MongoClient().db.translocations
    oid = ObjectId()
    first = {"Gene_Name": "A", "Feature_ID": "ENST000001"}
    second = {"Gene_Name": "A", "Feature_ID": "ENST000002"}
    original = [first, second]
    collection.insert_one(
        {
            "_id": oid,
            "SAMPLE_ID": "sample",
            "INFO": {"ANN": original, "MANE_ANN": first, "SVTYPE": "DEL"},
        }
    )
    repo = TranslocsRepository.__new__(TranslocsRepository)
    repo.get_collection = lambda: collection
    repo.invalidate_dashboard_metrics = Mock()
    assert repo.select_annotation(str(oid), "other", original, second).matched_count == 0
    assert repo.select_annotation(str(oid), "sample", original, second).matched_count == 1
    info = collection.find_one()["INFO"]
    assert info["ANN"] == [second, first]
    assert info["ANN_selection_source"] == "manual_override"
    assert "MANE_ANN" not in info
    assert info["SVTYPE"] == "DEL"
    assert repo.select_annotation(str(oid), "sample", original, first).matched_count == 0


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
