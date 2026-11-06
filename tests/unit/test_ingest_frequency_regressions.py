"""Regression coverage for numeric VEP field normalization."""

from coyote3.application.ingest.json_resources import read_ingest_json
from coyote3.application.ingest.parsers import _emulate_perl, _max_gnomad, _pick_af_fields


def test_utf8_bom_json_resource_is_readable(tmp_path):
    """UTF-8 byte order marks do not invalidate otherwise valid JSON resources."""
    source = tmp_path / "synthetic.json"
    source.write_text('{"value": 0}', encoding="utf-8-sig")
    assert read_ingest_json(str(source), "Synthetic") == {"value": 0}


def test_gnomad_maximum_compares_numbers_not_text():
    """Scientific notation must be ordered numerically."""
    assert _max_gnomad("9e-5&0.1") == 0.1


def test_mixed_annotation_values_are_not_partially_coerced():
    """A mixed text annotation is preserved rather than raising during ingest."""
    payload = {"INFO": {"CSQ": [{"SCORE": "0.1&."}]}}
    assert _emulate_perl(payload)["INFO"]["CSQ"][0]["SCORE"] == "0.1&."


def test_numeric_annotation_maximum_still_accepts_integer_and_exponent_tokens():
    """Preserve established normalization of mixed numeric representations."""
    payload = {"INFO": {"CSQ": [{"SCORE": "0.1&1&9e-2"}]}}
    assert _emulate_perl(payload)["INFO"]["CSQ"][0]["SCORE"] == 1.0


def test_measured_zero_population_frequency_survives_normalization():
    """An explicitly measured zero does not become an absent frequency."""
    payload = {"ALT": "G", "INFO": {"CSQ": [{"gnomAD_AF": "0.0", "MAX_AF": "0.0"}]}}
    result = _pick_af_fields(_emulate_perl(payload))
    assert result["gnomad_frequency"] == 0.0
    assert result["gnomad_max"] == 0.0
