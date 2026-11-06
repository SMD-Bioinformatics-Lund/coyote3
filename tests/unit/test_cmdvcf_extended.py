"""Tests for plain-dictionary VCF parsing helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pysam import VariantHeader

from coyote3.domain.common.parsers import cmdvcf


def test_missing_genotype_alleles_use_vcf_missing_marker():
    """Missing alleles remain missing rather than becoming literal None text."""
    rows, _ = cmdvcf.fix_gt({"CASE": {"GT": (None, 1)}}, ["CASE"])
    assert rows[0]["GT"] == "./1"


def test_phased_genotypes_retain_phase_separator():
    """Phasing is preserved in the persisted genotype string."""
    header = VariantHeader()
    header.contigs.add("1")
    header.add_sample("CASE")
    header.formats.add("GT", 1, "String", "Genotype")
    record = header.new_record(contig="1", start=1, alleles=("A", "G"))
    record.samples["CASE"]["GT"] = (0, 1)
    record.samples["CASE"].phased = True
    rows, _ = cmdvcf.fix_gt(dict(record.samples), ["CASE"])
    assert rows[0]["GT"] == "0|1"


@pytest.mark.parametrize("field,key", [("CSQ", "SYMBOL"), ("ANN", "Gene")])
def test_scalar_annotation_field_is_one_annotation(field, key):
    """Number-one annotation fields must not be split into individual characters."""
    result = cmdvcf.fix_info({field: "A|missense_variant|SYNTHETIC"}, _header())
    assert result[field][0][key] == "SYNTHETIC"


def test_csq_header_ignores_trailing_whitespace():
    """Valid descriptions with trailing whitespace retain their annotation fields."""
    header = _header()
    header.info["CSQ"].description += "  "
    assert cmdvcf.csq(["A|missense_variant|SYNTHETIC"], header)[0]["SYMBOL"] == "SYNTHETIC"


def test_snpeff_quoted_format_does_not_include_quote_in_last_key():
    """SnpEff's quoted format description must not become a quoted field name."""
    header = _header()
    header.info["ANN"].description = "Functional annotations: 'Allele | Annotation | Gene'"
    assert cmdvcf.snpeff(["A|missense_variant|SYNTHETIC"], header)[0]["Gene"] == "SYNTHETIC"


def test_parse_vcf_closes_file_on_parser_failure(monkeypatch):
    """Failed parsing must release its descriptor immediately."""
    source = Mock(header=_header())
    source.fetch.side_effect = ValueError("invalid VCF")
    monkeypatch.setattr(cmdvcf, "VariantFile", lambda _: source)
    with pytest.raises(ValueError):
        cmdvcf.parse_vcf("synthetic.vcf")
    source.close.assert_called_once()


def _header():
    return SimpleNamespace(
        samples=["CASE", "CONTROL"],
        info={
            "CSQ": SimpleNamespace(description="Format: Allele|Consequence|SYMBOL"),
            "ANN": SimpleNamespace(description="Allele | Annotation | Gene"),
        },
    )


def test_fix_gt_normalizes_genotypes_and_tuple_values() -> None:
    gt, format_fields = cmdvcf.fix_gt(
        {
            "CASE": {"GT": (0, 1), "AD": (10, 4), "DP": 14},
            "CONTROL": {"GT": (0, 0), "AD": (12, 0), "DP": 12},
        },
        ["CASE", "CONTROL"],
    )
    assert format_fields == ["GT", "AD", "DP"]
    assert gt[0] == {"GT": "0/1", "AD": "10,4", "DP": 14, "_sample_id": "CASE"}
    assert gt[1]["GT"] == "0/0"


def test_annotation_decoders_split_multi_consequence_terms() -> None:
    header = _header()
    assert cmdvcf.csq(["A|missense_variant&splice_region_variant|TP53"], header) == [
        {
            "Allele": "A",
            "Consequence": ["missense_variant", "splice_region_variant"],
            "SYMBOL": "TP53",
        }
    ]
    assert cmdvcf.snpeff(["A|missense_variant&splice_region_variant|TP53"], header) == [
        {
            "Allele": "A",
            "Annotation": ["missense_variant", "splice_region_variant"],
            "Gene": "TP53",
        }
    ]


def test_fix_info_handles_csq_ann_tuple_and_scalar_fields() -> None:
    observed = cmdvcf.fix_info(
        {
            "CSQ": ("T|missense_variant|TP53",),
            "ANN": ("T|missense_variant|TP53",),
            "CALLERS": ("freebayes", "vardict"),
            "DP": 100,
        },
        _header(),
    )
    assert observed["CSQ"][0]["SYMBOL"] == "TP53"
    assert observed["ANN"][0]["Gene"] == "TP53"
    assert observed["CALLERS"] == "freebayes,vardict"
    assert observed["DP"] == 100


def test_parse_variant_builds_coyote_shape_and_missing_id() -> None:
    record = SimpleNamespace(
        id=None,
        chrom="17",
        pos=10,
        ref="C",
        alts=("T",),
        qual=99.0,
        filter={"PASS": True},
        info={"DP": 42},
        samples={
            "CASE": {"GT": (0, 1), "DP": 42},
            "CONTROL": {"GT": (0, 0), "DP": 40},
        },
    )
    observed = cmdvcf.parse_variant(record, _header())
    assert observed["ID"] == "."
    assert observed["ALT"] == "T"
    assert observed["FILTER"] == "PASS"
    assert observed["FORMAT"] == ["GT", "DP"]
    assert observed["GT"][0]["_sample_id"] == "CASE"


def test_parse_vcf_closes_over_variant_file(monkeypatch) -> None:
    header = _header()
    record = SimpleNamespace(
        id="rs1",
        chrom="1",
        pos=2,
        ref="A",
        alts=("G",),
        qual=10,
        filter={},
        info={},
        samples={"CASE": {"GT": (0, 1)}, "CONTROL": {"GT": (0, 0)}},
    )
    monkeypatch.setattr(
        cmdvcf,
        "VariantFile",
        lambda path: SimpleNamespace(
            header=header, fetch=lambda: iter([record]), close=lambda: None
        ),
    )
    observed_header, rows = cmdvcf.parse_vcf("input.vcf")
    assert observed_header is header
    assert rows[0]["ID"] == "rs1"


def test_unravel_tuples_handles_strings_numbers_and_mixed_tuple() -> None:
    assert cmdvcf.unravel_tuples("text") == "text"
    assert cmdvcf.unravel_tuples(3) == 3
    assert cmdvcf.unravel_tuples((1, None, "x")) == "1,None,x"
