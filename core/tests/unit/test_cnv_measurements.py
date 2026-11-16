"""CNV measurements retain caller meaning and reject invalid clinical numbers."""

import json
import math

import pytest
from coyote.application.dna.export import build_cnv_export_rows
from coyote.application.dna.structural_variants import _cnv_sort_value
from coyote.application.ingest.analysis_parsers import DnaIngestParser
from coyote.application.reporting.smd_input import _summary_copy_number
from coyote.contracts.schemas.registry import normalize_collection_document
from coyote.domain.dna.cnv_metrics import copy_number_from_log2


def _row(ratio, **fields):
    """Build a synthetic interval without any persistence or review state."""
    return {"chr": "1", "start": 1, "end": 2, "size": 1, "ratio": ratio, **fields}


@pytest.mark.parametrize(
    "ratio",
    [True, False, math.nan, math.inf, -math.inf, "nan", "inf", "-inf", "1e400", 10**400],
)
def test_invalid_numeric_inputs_fail_both_ingest_and_collection_boundaries(ratio):
    """Neither parser normalization nor direct collection writes can conceal invalid input."""
    with pytest.raises(ValueError, match="Copy-number ratio"):
        DnaIngestParser._parse_cnvs_only([_row(ratio)])
    with pytest.raises(ValueError, match="Copy-number ratio"):
        normalize_collection_document("cnvs", _row(ratio, SAMPLE_ID="SYNTHETIC"))


def test_json_boolean_does_not_become_a_reportable_numeric_ratio():
    """The JSON boolean fails before it can be normalized to a plausible 1.0 ratio."""
    incoming = json.loads('{"chr":"1","start":1,"end":2,"size":1,"ratio":true}')
    with pytest.raises(ValueError, match="boolean"):
        DnaIngestParser._parse_cnvs_only([incoming])


@pytest.mark.parametrize(
    "caller,ratio,event,expected_copy",
    [("cnvkit", 0.5, "gain", "2.82"), ("gatk", 1, "AMP", "4.0"), ("manta", None, "DEL", "-")],
)
def test_numeric_measurement_and_textual_event_remain_distinct(caller, ratio, event, expected_copy):
    """An explicit event label is preserved and never supplies a missing measurement."""
    parsed = DnaIngestParser._parse_cnvs_only([_row(ratio, type=event, callers=[caller])])[0]
    normalized = normalize_collection_document("cnvs", {**parsed, "SAMPLE_ID": "SYNTHETIC"})
    assert normalized["ratio"] == ratio
    assert normalized["type"] == event
    assert normalized["callers"] == [caller]
    assert _summary_copy_number(normalized["ratio"]) == expected_copy
    if ratio is None:
        assert _cnv_sort_value(normalized, "copy_number") is None
    else:
        assert _cnv_sort_value(normalized, "copy_number") == 2 * (2**ratio)


@pytest.mark.parametrize("ratio", [True, False, math.nan, math.inf, -math.inf, 1023.0, 1024.0])
def test_unusable_existing_values_do_not_break_analysis_sorting_or_report_display(ratio):
    """Reading old malformed or overflowing values does not fabricate numeric results."""
    assert _cnv_sort_value(_row(ratio), "copy_number") is None
    assert _cnv_sort_value(_row(ratio), "purity") is None
    assert _summary_copy_number(ratio) == "-"
    exported = build_cnv_export_rows([_row(ratio)], {"purity": 0.5}, "solid")[0]
    assert exported.purity_copy_number == ""
    assert "(" not in exported.copy_number


@pytest.mark.parametrize("ratio", [0, 1, -1, 0.5])
def test_copy_number_preserves_the_valid_diploid_calculation(ratio):
    assert copy_number_from_log2(ratio) == 2 * (2**ratio)


@pytest.mark.parametrize("ratio", [True, False, "1", None])
def test_copy_number_rejects_nonmeasurement_types(ratio):
    with pytest.raises(TypeError, match="numeric"):
        copy_number_from_log2(ratio)


@pytest.mark.parametrize("ratio", [math.nan, math.inf, -math.inf])
def test_copy_number_rejects_nonfinite_measurements(ratio):
    with pytest.raises(ValueError, match="finite"):
        copy_number_from_log2(ratio)


@pytest.mark.parametrize("ratio", [1023.0, 1024.0])
def test_copy_number_detects_overflow_in_exponent_and_final_multiplication(ratio):
    with pytest.raises(OverflowError):
        copy_number_from_log2(ratio)
