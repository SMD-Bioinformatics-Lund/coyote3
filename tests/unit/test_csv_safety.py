"""CSV cells remain data rather than executable formulas, including zero measurements."""

import csv
from io import StringIO

import pytest
from pydantic import BaseModel

from api.application.dna.export import export_rows_to_csv, protect_excel, safe_text
from api.domain.common.csv_safety import spreadsheet_text


@pytest.mark.parametrize(
    "value", ["=1+1", "+SUM(1)", "-1+2", "@SUM(1)", "  =1", "\tformula", "\rformula"]
)
def test_formula_and_control_prefixes_are_text(value):
    assert spreadsheet_text(value) == "'" + value


@pytest.mark.parametrize("value", [0, -0.3, "-0.3", "1e-4", "TP53", ""])
def test_numeric_measurements_and_gene_symbols_are_unchanged(value):
    assert spreadsheet_text(value) == str(value)


def test_backend_export_retains_zero_and_escapes_formula():
    class Row(BaseModel):
        depth: int
        comment: str

    assert safe_text(0) == "0"
    assert safe_text(None) == ""
    assert spreadsheet_text(None) == ""
    assert protect_excel("01") == "'01"
    result = list(csv.DictReader(StringIO(export_rows_to_csv([Row(depth=0, comment="=1+1")]))))
    assert result == [{"depth": "0", "comment": "'=1+1"}]
