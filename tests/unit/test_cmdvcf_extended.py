"""Tests for plain-dictionary VCF parsing helpers."""

from __future__ import annotations

from types import SimpleNamespace

from api.domain.common.parsers import cmdvcf


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
        lambda path: SimpleNamespace(header=header, fetch=lambda: iter([record])),
    )
    observed_header, rows = cmdvcf.parse_vcf("input.vcf")
    assert observed_header is header
    assert rows[0]["ID"] == "rs1"


def test_unravel_tuples_handles_strings_numbers_and_mixed_tuple() -> None:
    assert cmdvcf.unravel_tuples("text") == "text"
    assert cmdvcf.unravel_tuples(3) == 3
    assert cmdvcf.unravel_tuples((1, None, "x")) == "1,None,x"
