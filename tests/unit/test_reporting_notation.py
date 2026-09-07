"""Tests for stable reporting language and HGVS residue notation helpers."""

from api.domain.common.reporting import nl_num
from api.domain.core.dna.notation import one_letter_p, three_letter_p


def test_swedish_small_numbers_respect_neuter_form_and_bounds():
    """Approved report-number wording is deterministic and does not index negatively."""
    assert nl_num(1, "n") == "en"
    assert nl_num(1, "t") == "ett"
    assert nl_num(12, "n") == "tolv"
    assert nl_num(13, "n") == "13"
    assert nl_num(-1, "n") == "-1"


def test_protein_hgvs_converts_between_supported_one_and_three_letter_forms():
    """HGVS substitutions use the shared, canonical amino-acid mapping."""
    assert one_letter_p("p.Arg175His") == "p.R175H"
    assert one_letter_p("p.Ter12Gln") == "p.*12Q"
    assert three_letter_p("p.R175H") == "p.Arg175His"
    assert three_letter_p("p.*12Q") == "p.Ter12Gln"


def test_three_letter_protein_conversion_preserves_non_substitution_hgvs():
    """Unsupported complex HGVS is not heuristically rewritten."""
    assert three_letter_p("p.Arg175del") == "p.Arg175del"
