"""CNV gene eligibility across selected lists, panel fallback and reports."""

from copy import deepcopy

import pytest
from coyote.application.reporting.dna.selection import _filter_cnvs_for_report
from coyote.domain.dna.cnv_selection import CnvGeneScope


@pytest.mark.parametrize(
    "panel_genes,selected,documents,expected,restricted",
    [
        ([], [], {}, ["A", "B"], False),
        (None, [], {}, ["A", "B"], False),
        (["A"], [], {}, ["A"], True),
        (["A", "B"], ["focus"], {"focus": {"genes": ["B"]}}, ["B"], True),
        ([], ["focus"], {"focus": {"genes": ["B"]}}, ["B"], True),
        (["A"], ["focus"], {"focus": {"genes": ["B"]}}, [], True),
        ([], ["focus"], {"focus": {"genes": []}}, [], True),
        ([], ["missing"], {}, [], True),
        ([], ["focus"], {"focus": {"genes": ["B"], "is_active": False}}, [], True),
    ],
)
def test_cnv_gene_scope_preserves_explicit_empty_selection(
    panel_genes, selected, documents, expected, restricted
):
    """Unrestricted CNVs are distinct from an explicit selection with no eligible genes."""
    sample = {"filters": {"somatic": {"cnv": {"cnvlists": selected}}}}
    lists = {
        key: {"list_type": ["cnv"], "is_active": True, **doc} for key, doc in documents.items()
    }
    original = deepcopy((sample, lists))
    scope = CnvGeneScope.resolve(sample, {"covered_genes": panel_genes}, lists)
    findings = [{"_id": gene, "ratio": 0.5, "genes": [{"gene": gene}]} for gene in ["A", "B"]]
    rows = _filter_cnvs_for_report(
        findings,
        sample_filters=sample["filters"],
        filter_genes=list(scope.genes),
        restricted=scope.restricted,
    )
    assert [row["_id"] for row in rows] == expected
    assert scope.restricted is restricted
    assert (sample, lists) == original


def test_cnv_adhoc_scope_applies_without_panel_genes():
    sample = {"filters": {"somatic": {"cnv": {"adhoc_genes": {"genes": ["B"]}}}}}
    scope = CnvGeneScope.resolve(sample, {}, {})
    assert scope.genes == ("B",)
    assert scope.restricted
